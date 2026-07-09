#!/usr/bin/env python3
"""Optional xelatex rendering checks for quality audits."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from quality_checks import latex_fields
from quality_core import QualityIssue, QuestionRecord, SEVERITY_ORDER


TOOL_VERSION = "quality-render-v1"


@dataclass(frozen=True)
class RenderOptions:
    mode: str = "sample"
    output_dir: Path = Path("analysis")
    sample_size: int = 25
    timeout_seconds: int = 30
    keep_workdir: bool = False

    @property
    def cache_dir(self) -> Path:
        return self.output_dir / "quality_render_cache"


@dataclass(frozen=True)
class RenderResult:
    success: bool
    returncode: int
    log_excerpt: str
    tex_path: Optional[Path] = None
    log_path: Optional[Path] = None


def build_render_document(record: QuestionRecord) -> str:
    body_parts = [rf"\section*{{{_latex_escape(record.id)}}}"]
    for field, text in latex_fields(record):
        body_parts.append(rf"\subsection*{{{_latex_escape(field)}}}")
        body_parts.append(text)
    return RENDER_PREAMBLE + "\n".join(body_parts) + "\n\\end{document}\n"


def render_cache_key(record: QuestionRecord, document: str) -> str:
    payload = "\n".join([TOOL_VERSION, record.id, RENDER_PREAMBLE, document])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def select_records_for_render(
    records: List[QuestionRecord],
    issues: List[QualityIssue],
    mode: str,
    sample_size: int,
) -> List[QuestionRecord]:
    if mode == "off":
        return []
    if mode == "full":
        return list(records)
    if mode != "sample":
        raise ValueError(f"unknown render mode: {mode}")

    risky_ids = {
        issue.question_id
        for issue in issues
        if issue.question_id and SEVERITY_ORDER[issue.severity] >= SEVERITY_ORDER["medium"]
    }
    risky_ids.update(record.id for record in records if record.review_flag == "clean_required")
    risky = [record for record in records if record.id in risky_ids]
    risky_seen = {record.id for record in risky}
    remaining = [record for record in sorted(records, key=lambda item: item.id) if record.id not in risky_seen]
    return sorted(risky + remaining[:sample_size], key=lambda item: item.id)


def run_render_checks(
    records: List[QuestionRecord],
    existing_issues: List[QualityIssue],
    options: RenderOptions,
    runner: Optional[Callable[..., Any]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> List[QualityIssue]:
    selected = select_records_for_render(records, existing_issues, options.mode, options.sample_size)
    if not selected:
        return []

    which = which or shutil.which
    xelatex = which("xelatex")
    if not xelatex:
        return [
            QualityIssue(
                id="render.missing_xelatex",
                severity="critical",
                question_id="",
                field="render",
                message="xelatex is required for render checks but was not found in PATH",
                evidence={"render_mode": options.mode},
            )
        ]

    options.cache_dir.mkdir(parents=True, exist_ok=True)
    runner = runner or subprocess.run
    issues: List[QualityIssue] = []

    for record in selected:
        document = build_render_document(record)
        key = render_cache_key(record, document)
        cache_path = options.cache_dir / f"{key}.json"
        cached = _read_cache(cache_path)
        if cached and cached.get("success") is True:
            continue

        result = _compile_document(record, document, Path(xelatex), options, runner)
        _write_cache(cache_path, result)
        if not result.success:
            artifacts: Dict[str, Path] = {}
            if result.tex_path:
                artifacts["tex"] = result.tex_path
            if result.log_path:
                artifacts["log"] = result.log_path
            issues.append(
                QualityIssue(
                    id="render.compile_failed",
                    severity="critical",
                    question_id=record.id,
                    field="render",
                    message=f"LaTeX render failed: {result.log_excerpt}",
                    evidence={"returncode": result.returncode},
                    source_path=record.source_path,
                    render_artifacts=artifacts,
                )
            )
    return issues


def _compile_document(
    record: QuestionRecord,
    document: str,
    xelatex: Path,
    options: RenderOptions,
    runner: Callable[..., Any],
) -> RenderResult:
    if options.keep_workdir:
        parent = options.output_dir / "quality_render_work"
        parent.mkdir(parents=True, exist_ok=True)
        cleanup_dir = None
    else:
        cleanup_dir = tempfile.TemporaryDirectory(prefix="quality-render-")
        parent = Path(cleanup_dir.name)

    tex_path = parent / f"{_safe_filename(record.id)}.tex"
    tex_path.write_text(document, encoding="utf-8")

    try:
        completed = runner(
            [
                str(xelatex),
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(parent),
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            timeout=options.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        if cleanup_dir is not None:
            cleanup_dir.cleanup()
        return RenderResult(False, 124, f"xelatex timed out after {options.timeout_seconds}s", tex_path if options.keep_workdir else None, None)

    log_path = parent / f"{tex_path.stem}.log"
    output = "\n".join([str(getattr(completed, "stdout", "")), str(getattr(completed, "stderr", ""))]).strip()
    excerpt = _log_excerpt(output)

    if cleanup_dir is not None:
        cleanup_dir.cleanup()

    return RenderResult(
        success=completed.returncode == 0,
        returncode=int(completed.returncode),
        log_excerpt=excerpt,
        tex_path=tex_path if options.keep_workdir else None,
        log_path=log_path if options.keep_workdir and log_path.exists() else None,
    )


def _read_cache(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_cache(path: Path, result: RenderResult) -> None:
    path.write_text(
        json.dumps(
            {
                "success": result.success,
                "returncode": result.returncode,
                "log_excerpt": result.log_excerpt,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _log_excerpt(output: str, limit: int = 500) -> str:
    if not output:
        return "no xelatex output"
    marker = "! "
    if marker in output:
        output = output[output.index(marker) :]
    return output[-limit:]


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)[:120]


def _latex_escape(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("#", r"\#")


RENDER_PREAMBLE = r"""\documentclass[border=10pt]{standalone}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{unicode-math}
\usepackage[fontset=fandol]{ctex}
\usepackage{xcolor}
\usepackage{ulem}
\usepackage{pifont}
\usepackage{tikz}
\usepackage{enumitem}
\usepackage{array}
\usepackage{tabularx}
\usetikzlibrary{positioning, calc, shapes.geometric, arrows.meta}
\DeclareMathOperator{\dif}{\mathop{}\!\mathrm{d}}
\DeclareMathOperator{\upe}{\operatorname{e}}
\renewcommand{\le}{\leqslant}
\renewcommand{\leq}{\leqslant}
\renewcommand{\ge}{\geqslant}
\renewcommand{\geq}{\geqslant}
\newcommand{\blank}[1]{\underline{\hspace{3em}}}
\begin{document}
"""
