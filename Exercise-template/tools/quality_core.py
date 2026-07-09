#!/usr/bin/env python3
"""Core models and YAML loading for question quality audits."""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from question_loader import load_question_file


DEFAULT_BANK = Path("bank/_curated/amm_analysis_training_full_zh")
DEFAULT_OUTPUT_DIR = Path("analysis")
SEVERITY_ORDER: Dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}
ACCEPTED_RECORD_TYPES_V1 = ("choice", "fillin", "solution")


@dataclass(frozen=True)
class QuestionRecord:
    id: str
    source_path: Path
    source_metadata: Dict[str, Any] = dc_field(default_factory=dict)
    schema_version: Optional[int] = None
    status: str = ""
    type: str = ""
    stem_latex: str = ""
    choices: List[Dict[str, Any]] = dc_field(default_factory=list)
    answers: List[Dict[str, Any]] = dc_field(default_factory=list)
    explanation_latex: str = ""
    solution_latex: str = ""
    comment: str = ""
    metadata: Dict[str, Any] = dc_field(default_factory=dict)
    raw: Dict[str, Any] = dc_field(default_factory=dict)

    @property
    def review_flag(self) -> str:
        curation = self.metadata.get("curation", {})
        if isinstance(curation, dict) and curation.get("review_flag"):
            return str(curation["review_flag"])
        return ""

    @property
    def translation_review_status(self) -> str:
        translation = self.metadata.get("translation", {})
        if isinstance(translation, dict) and translation.get("review_status"):
            return str(translation["review_status"])
        return ""


@dataclass(frozen=True)
class QualityIssue:
    id: str
    severity: str
    question_id: str = ""
    field: str = ""
    message: str = ""
    evidence: Any = ""
    source_path: Optional[Path] = None
    source_line: Optional[int] = None
    render_artifacts: Dict[str, Path] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_ORDER:
            raise ValueError(f"unknown severity: {self.severity}")


def normalize_question(raw: Dict[str, Any], source_path: Path) -> QuestionRecord:
    source = raw.get("source", {})
    metadata = raw.get("metadata", {})
    return QuestionRecord(
        id=_text_or_empty(raw.get("id")),
        source_path=source_path,
        source_metadata=dict(source) if isinstance(source, dict) else {},
        schema_version=raw.get("schema_version") if isinstance(raw.get("schema_version"), int) else None,
        status=_text_or_empty(raw.get("status")),
        type=_text_or_empty(raw.get("type")),
        stem_latex=_text_or_empty(raw.get("stem_latex")),
        choices=list(raw.get("choices", []) or []),
        answers=list(raw.get("answers", []) or []),
        explanation_latex=_text_or_empty(raw.get("explanation_latex")),
        solution_latex=_text_or_empty(raw.get("solution_latex")),
        comment=_text_or_empty(raw.get("comment")),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
        raw=raw,
    )


def load_yaml_bank(bank_root: Path) -> Tuple[List[QuestionRecord], List[QualityIssue]]:
    records: List[QuestionRecord] = []
    issues: List[QualityIssue] = []
    for path in sorted(Path(bank_root).glob("**/*.yaml")):
        try:
            records.append(normalize_question(load_question_file(path), path))
        except Exception as exc:
            issues.append(
                QualityIssue(
                    id="source.yaml_parse_error",
                    severity="critical",
                    question_id="",
                    field="",
                    message=f"Could not parse YAML question file: {exc}",
                    evidence=type(exc).__name__,
                    source_path=path,
                )
            )
    return records, issues


def issue_dict(issue: QualityIssue) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": issue.id,
        "severity": issue.severity,
        "question_id": issue.question_id,
        "field": issue.field,
        "message": issue.message,
        "evidence": issue.evidence,
        "source_path": str(issue.source_path) if issue.source_path else "",
        "source_line": issue.source_line,
        "render_artifacts": {key: str(value) for key, value in issue.render_artifacts.items()},
    }
    return data


def should_fail(issues: Iterable[QualityIssue], fail_on: str = "high") -> bool:
    if fail_on not in SEVERITY_ORDER:
        raise ValueError(f"unknown fail threshold: {fail_on}")
    threshold = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER[issue.severity] >= threshold for issue in issues)


def _text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
