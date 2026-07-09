# Question Quality Audit Toolchain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable question-quality audit command that runs deterministic rule checks plus optional LaTeX rendering checks, writes JSON/JSONL/HTML reports, and fails only on high-risk issues.

**Architecture:** Add focused modules under `tools/`: a normalized model and YAML adapter, rule checkers, render checker with cache, reporters, and a thin CLI entry point. Version 1 audits YAML banks first, while keeping the checker interfaces source-agnostic so a THUExam `.tex` adapter can be added without rewriting quality rules.

**Tech Stack:** Python 3 stdlib only; existing `question_loader.py`; optional local `xelatex` only when render mode is `sample` or `full`; pytest for tests.

## Global Constraints

- Default source bank is `bank/_curated/amm_analysis_training_full_zh`.
- Default output directory is `analysis`.
- Supported render modes are exactly `off`, `sample`, and `full`.
- Default render mode is `sample`.
- Default failing threshold is `high`; `critical` and `high` make the command return non-zero.
- `medium` and `low` issues are report-only.
- Normal pytest suite must not require a local TeX installation.
- Version 1 accepted record types are exactly `choice`, `fillin`, and `solution`.
- Reuse `question_loader.load_question_file` for YAML parsing.
- Reuse `tools/pdf_generator.py` package conventions for render preamble content.
- Reports must be written as `quality_audit.json`, `quality_audit.jsonl`, and `quality_audit.html`.

---

## File Structure

- Create `tools/quality_core.py`: dataclasses, severity ordering, YAML-bank loading, normalization, and gate helpers.
- Create `tools/quality_checks.py`: deterministic rule checkers for schema, type consistency, LaTeX text, known bad patterns, content completeness, and review state.
- Create `tools/quality_render.py`: LaTeX render-document builder, sample/full selection, cache keying, and subprocess-backed compile checks.
- Create `tools/quality_reports.py`: summary generation and JSON/JSONL/HTML report writers.
- Create `tools/quality_audit.py`: CLI parser and orchestration.
- Create `tests/test_quality_core.py`: normalized model, YAML adapter, and gate tests.
- Create `tests/test_quality_checks.py`: rule-checker tests.
- Create `tests/test_quality_render.py`: render-document, selection, cache, and fake-runner tests.
- Create `tests/test_quality_reports.py`: JSON/JSONL/HTML report tests.
- Create `tests/test_quality_audit_cli.py`: CLI integration tests using temporary YAML banks.

---

### Task 1: Core Model, YAML Adapter, And Gate Helpers

**Files:**
- Create: `tools/quality_core.py`
- Test: `tests/test_quality_core.py`

**Interfaces:**
- Produces: `QuestionRecord` dataclass.
- Produces: `QualityIssue` dataclass.
- Produces: `SEVERITY_ORDER: dict[str, int]`.
- Produces: `DEFAULT_BANK = Path("bank/_curated/amm_analysis_training_full_zh")`.
- Produces: `normalize_question(raw: dict[str, Any], source_path: Path) -> QuestionRecord`.
- Produces: `load_yaml_bank(bank_root: Path) -> tuple[list[QuestionRecord], list[QualityIssue]]`.
- Produces: `issue_dict(issue: QualityIssue) -> dict[str, Any]`.
- Produces: `should_fail(issues: Iterable[QualityIssue], fail_on: str = "high") -> bool`.
- Consumes: `question_loader.load_question_file(path: Path) -> dict[str, Any]`.

- [ ] **Step 1: Write failing core tests**

Create `tests/test_quality_core.py`:

```python
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def write_yaml(path: Path, record: dict) -> None:
    from legacy_yaml_exporter import record_to_yaml

    path.write_text(record_to_yaml(record), encoding="utf-8")


def test_normalize_question_preserves_expected_fields(tmp_path):
    from quality_core import normalize_question

    record = {
        "schema_version": 1,
        "id": "imported.demo.q001",
        "status": "draft",
        "type": "choice",
        "source": {"file": "examples/demo.tex", "line": 38},
        "stem_latex": "Find $x$.",
        "choices": [{"key": "opt1", "text_latex": "$1$", "correct": True}],
        "explanation_latex": "Because $x=1$.",
        "metadata": {"curation": {"review_flag": "auto_ok"}},
    }

    normalized = normalize_question(record, tmp_path / "q001.yaml")

    assert normalized.id == "imported.demo.q001"
    assert normalized.type == "choice"
    assert normalized.source_path.name == "q001.yaml"
    assert normalized.source_metadata["line"] == 38
    assert normalized.choices[0]["key"] == "opt1"
    assert normalized.answers == []
    assert normalized.solution_latex == ""
    assert normalized.review_flag == "auto_ok"


def test_load_yaml_bank_returns_records_and_parse_issues(tmp_path):
    from quality_core import load_yaml_bank

    good = {
        "schema_version": 1,
        "id": "imported.demo.q001",
        "status": "draft",
        "type": "solution",
        "source": {"file": "examples/demo.tex"},
        "stem_latex": "Compute $1+1$.",
        "solution_latex": "$2$",
    }
    write_yaml(tmp_path / "q001.yaml", good)
    (tmp_path / "broken.yaml").write_text("id: imported.demo.q002\n  bad_indent: true\n", encoding="utf-8")

    records, issues = load_yaml_bank(tmp_path)

    assert [record.id for record in records] == ["imported.demo.q001"]
    assert len(issues) == 1
    assert issues[0].id == "source.yaml_parse_error"
    assert issues[0].severity == "critical"
    assert issues[0].source_path.name == "broken.yaml"


def test_should_fail_respects_threshold():
    from quality_core import QualityIssue, should_fail

    medium = QualityIssue(id="review.needs_review", severity="medium", question_id="q1")
    high = QualityIssue(id="review.clean_required", severity="high", question_id="q2")

    assert should_fail([medium], fail_on="high") is False
    assert should_fail([medium], fail_on="medium") is True
    assert should_fail([high], fail_on="high") is True


def test_issue_dict_uses_serializable_paths(tmp_path):
    from quality_core import QualityIssue, issue_dict

    issue = QualityIssue(
        id="schema.missing_stem",
        severity="critical",
        question_id="imported.demo.q001",
        field="stem_latex",
        message="Missing stem",
        evidence={"field": "stem_latex"},
        source_path=tmp_path / "q001.yaml",
        source_line=12,
        render_artifacts={"log": tmp_path / "q001.log"},
    )

    data = issue_dict(issue)
    json.dumps(data)

    assert data["source_path"].endswith("q001.yaml")
    assert data["render_artifacts"]["log"].endswith("q001.log")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_quality_core.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'quality_core'`.

- [ ] **Step 3: Implement core module**

Create `tools/quality_core.py`:

```python
#!/usr/bin/env python3
"""Core models and YAML loading for question quality audits."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from question_loader import load_question_file


DEFAULT_BANK = Path("bank/_curated/amm_analysis_training_full_zh")
DEFAULT_OUTPUT_DIR = Path("analysis")
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class QuestionRecord:
    id: str
    source_path: Path
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: Optional[int] = None
    status: str = ""
    type: str = ""
    stem_latex: str = ""
    choices: List[Dict[str, Any]] = field(default_factory=list)
    answers: List[Dict[str, Any]] = field(default_factory=list)
    explanation_latex: str = ""
    solution_latex: str = ""
    comment: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

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
    render_artifacts: Dict[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_ORDER:
            raise ValueError(f"unknown severity: {self.severity}")


def normalize_question(raw: Dict[str, Any], source_path: Path) -> QuestionRecord:
    source = raw.get("source", {})
    metadata = raw.get("metadata", {})
    return QuestionRecord(
        id=str(raw.get("id", "")),
        source_path=source_path,
        source_metadata=dict(source) if isinstance(source, dict) else {},
        schema_version=raw.get("schema_version") if isinstance(raw.get("schema_version"), int) else None,
        status=str(raw.get("status", "")),
        type=str(raw.get("type", "")),
        stem_latex=str(raw.get("stem_latex", "")),
        choices=list(raw.get("choices", []) or []),
        answers=list(raw.get("answers", []) or []),
        explanation_latex=str(raw.get("explanation_latex", "")),
        solution_latex=str(raw.get("solution_latex", "")),
        comment=str(raw.get("comment", "")),
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
```

- [ ] **Step 4: Run core tests**

Run:

```bash
python3 -m pytest tests/test_quality_core.py -q
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/quality_core.py tests/test_quality_core.py
git commit -m "Add quality audit core model"
```

---

### Task 2: Deterministic Rule Checkers

**Files:**
- Create: `tools/quality_checks.py`
- Test: `tests/test_quality_checks.py`

**Interfaces:**
- Consumes: `QuestionRecord` and `QualityIssue` from `quality_core.py`.
- Produces: `run_rule_checks(records: Iterable[QuestionRecord]) -> list[QualityIssue]`.
- Produces checker functions:
  - `check_schema(record: QuestionRecord) -> list[QualityIssue]`
  - `check_type_consistency(record: QuestionRecord) -> list[QualityIssue]`
  - `check_latex_text(record: QuestionRecord) -> list[QualityIssue]`
  - `check_known_bad_patterns(record: QuestionRecord) -> list[QualityIssue]`
  - `check_content_completeness(record: QuestionRecord) -> list[QualityIssue]`
  - `check_review_state(record: QuestionRecord) -> list[QualityIssue]`
- Produces: `latex_fields(record: QuestionRecord) -> list[tuple[str, str]]`.

- [ ] **Step 1: Write failing checker tests**

Create `tests/test_quality_checks.py`:

```python
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def record(**overrides):
    from quality_core import QuestionRecord

    base = {
        "id": "imported.demo.q001",
        "source_path": Path("bank/q001.yaml"),
        "source_metadata": {"file": "examples/demo.tex"},
        "schema_version": 1,
        "status": "draft",
        "type": "solution",
        "stem_latex": "Compute $1+1$.",
        "solution_latex": "$2$",
        "metadata": {"curation": {"review_flag": "auto_ok"}},
    }
    base.update(overrides)
    return QuestionRecord(**base)


def issue_ids(issues):
    return [issue.id for issue in issues]


def test_schema_checker_flags_required_fields_and_unknown_type():
    from quality_checks import check_schema

    issues = check_schema(record(id="", type="essay", stem_latex=""))

    assert "schema.missing_id" in issue_ids(issues)
    assert "schema.missing_stem_latex" in issue_ids(issues)
    assert "schema.unknown_type" in issue_ids(issues)
    assert {issue.severity for issue in issues if issue.id.startswith("schema.missing")} == {"critical"}


def test_choice_checker_requires_exactly_one_correct_choice():
    from quality_checks import check_type_consistency

    issues = check_type_consistency(
        record(
            type="choice",
            choices=[
                {"key": "opt1", "text_latex": "$1$", "correct": True},
                {"key": "opt2", "text_latex": "$2$", "correct": True},
            ],
        )
    )

    assert issues[0].id == "type.choice_correct_count"
    assert issues[0].severity == "high"


def test_fillin_checker_matches_blank_keys_to_answer_keys():
    from quality_checks import check_type_consistency

    issues = check_type_consistency(
        record(
            type="fillin",
            stem_latex=r"Answer \blank{blank1} and \blank{blank2}.",
            answers=[{"key": "blank1", "latex": "$1$"}],
        )
    )

    assert issues[0].id == "type.fillin_blank_answer_mismatch"
    assert issues[0].severity == "high"
    assert "blank2" in str(issues[0].evidence)


def test_latex_checker_flags_unbalanced_math_and_environment():
    from quality_checks import check_latex_text

    issues = check_latex_text(record(stem_latex=r"Bad $x and \begin{align} x=1"))

    assert "latex.unbalanced_inline_math" in issue_ids(issues)
    assert "latex.unclosed_environment" in issue_ids(issues)
    assert {issue.severity for issue in issues} == {"critical"}


def test_latex_checker_flags_known_broken_command_and_json_wrapper():
    from quality_checks import check_latex_text

    issues = check_latex_text(record(stem_latex='{"text": "定义在 $\\nmathbb{R}$ 上"}'))

    assert "latex.jsonish_text_wrapper" in issue_ids(issues)
    assert "latex.broken_command_nmathbb" in issue_ids(issues)


def test_known_bad_pattern_checker_flags_amm_footer_material():
    from quality_checks import check_known_bad_patterns

    issues = check_known_bad_patterns(
        record(
            solution_latex=(
                r"\section*{Problems and Solutions}"
                "\nProposed problems and solutions should be sent in duplicate."
            )
        )
    )

    assert "content.unrelated_amm_page_material" in issue_ids(issues)
    assert issues[0].severity == "high"


def test_content_completeness_flags_clear_multi_part_mismatch():
    from quality_checks import check_content_completeness

    issues = check_content_completeness(
        record(
            stem_latex="(a) Prove the first claim. (b) Prove the second claim. (c) Find equality.",
            solution_latex="For (a), this follows immediately.",
        )
    )

    assert issues[0].id == "content.multipart_solution_mismatch"
    assert issues[0].severity == "high"


def test_review_state_checker_maps_review_flags():
    from quality_checks import check_review_state

    clean = record(metadata={"curation": {"review_flag": "clean_required"}})
    needs = record(metadata={"curation": {"review_flag": "needs_review"}})
    machine = record(status="machine_draft", metadata={"curation": {"review_flag": "auto_ok"}})

    assert check_review_state(clean)[0].severity == "high"
    assert check_review_state(needs)[0].severity == "medium"
    assert check_review_state(machine)[0].severity == "low"


def test_run_rule_checks_combines_checker_outputs():
    from quality_checks import run_rule_checks

    issues = run_rule_checks([record(type="choice", choices=[])])

    assert "type.choice_missing_choices" in issue_ids(issues)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_quality_checks.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'quality_checks'`.

- [ ] **Step 3: Implement deterministic checkers**

Create `tools/quality_checks.py`:

```python
#!/usr/bin/env python3
"""Deterministic quality checks for normalized question records."""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from quality_core import QualityIssue, QuestionRecord


ACCEPTED_TYPES = {"choice", "fillin", "solution"}
LATEX_ENV_RE = re.compile(r"\\(begin|end)\{([^}]+)\}")
BLANK_RE = re.compile(r"\\blank\{([^}]+)\}")
MULTIPART_RE = re.compile(r"\(([a-z])\)")
KNOWN_BAD_PATTERNS = [
    re.compile(r"Problems and Solutions", re.IGNORECASE),
    re.compile(r"Proposed problems and solutions should be sent", re.IGNORECASE),
    re.compile(r"submitted solutions should arrive", re.IGNORECASE),
    re.compile(r"edited by .{0,80}(Gerald|Ullman|West)", re.IGNORECASE | re.DOTALL),
    re.compile(r"\\section\*\{问题与解答\}"),
    re.compile(r"拟投稿的问题和解答应"),
]


def run_rule_checks(records: Iterable[QuestionRecord]) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    for record in records:
        issues.extend(check_schema(record))
        issues.extend(check_type_consistency(record))
        issues.extend(check_latex_text(record))
        issues.extend(check_known_bad_patterns(record))
        issues.extend(check_content_completeness(record))
        issues.extend(check_review_state(record))
    return issues


def check_schema(record: QuestionRecord) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    if not record.id:
        issues.append(_issue(record, "schema.missing_id", "critical", "id", "Missing question id"))
    if not record.type:
        issues.append(_issue(record, "schema.missing_type", "critical", "type", "Missing question type"))
    elif record.type not in ACCEPTED_TYPES:
        issues.append(_issue(record, "schema.unknown_type", "high", "type", f"Unknown question type: {record.type}"))
    if not record.stem_latex.strip():
        issues.append(_issue(record, "schema.missing_stem_latex", "critical", "stem_latex", "Missing question stem"))
    if record.schema_version is None:
        issues.append(_issue(record, "schema.missing_schema_version", "low", "schema_version", "Missing schema_version"))
    if not any(record.source_metadata.get(key) for key in ("file", "legacy_id", "translation_of")):
        issues.append(_issue(record, "schema.missing_source_metadata", "low", "source", "Missing source provenance"))
    return issues


def check_type_consistency(record: QuestionRecord) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    if record.type == "choice":
        if not record.choices:
            issues.append(_issue(record, "type.choice_missing_choices", "high", "choices", "Choice record has no choices"))
        correct_count = sum(1 for choice in record.choices if choice.get("correct") is True)
        if record.choices and correct_count != 1:
            issues.append(
                _issue(
                    record,
                    "type.choice_correct_count",
                    "high",
                    "choices",
                    "Choice record must have exactly one correct answer",
                    {"correct_count": correct_count},
                )
            )
        keys = [str(choice.get("key", "")) for choice in record.choices]
        if len(keys) != len(set(keys)):
            issues.append(_issue(record, "type.choice_duplicate_keys", "high", "choices", "Choice keys are not unique", keys))
    if record.type == "fillin":
        blank_keys = set(BLANK_RE.findall(record.stem_latex))
        answer_keys = {str(answer.get("key", "")) for answer in record.answers}
        if not record.answers:
            issues.append(_issue(record, "type.fillin_missing_answers", "high", "answers", "Fill-in record has no answers"))
        if blank_keys and blank_keys != answer_keys:
            issues.append(
                _issue(
                    record,
                    "type.fillin_blank_answer_mismatch",
                    "high",
                    "answers",
                    "Fill-in blank keys do not match answer keys",
                    {"blank_keys": sorted(blank_keys), "answer_keys": sorted(answer_keys)},
                )
            )
    if record.type == "solution" and not (record.solution_latex.strip() or record.explanation_latex.strip()):
        issues.append(_issue(record, "type.solution_missing_solution", "medium", "solution_latex", "Solution record has no solution text"))
    return issues


def check_latex_text(record: QuestionRecord) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    for field, text in latex_fields(record):
        if _unescaped_dollar_count(text) % 2:
            issues.append(_issue(record, "latex.unbalanced_inline_math", "critical", field, "Unbalanced inline dollar math"))
        if text.count(r"\[") != text.count(r"\]"):
            issues.append(_issue(record, "latex.unbalanced_bracket_display_math", "critical", field, "Unbalanced bracket display math"))
        if text.count("$$") % 2:
            issues.append(_issue(record, "latex.unbalanced_dollar_display_math", "critical", field, "Unbalanced dollar display math"))
        unclosed, unexpected = _environment_issues(text)
        for env in unexpected:
            issues.append(_issue(record, "latex.unexpected_end_environment", "critical", field, f"Unexpected end environment: {env}", env))
        for env in unclosed:
            issues.append(_issue(record, "latex.unclosed_environment", "critical", field, f"Unclosed LaTeX environment: {env}", env))
        if r"\nmathbb" in text:
            issues.append(_issue(record, "latex.broken_command_nmathbb", "high", field, r"Found broken command \nmathbb"))
        if '{"text"' in text or text.lstrip().startswith('{"text"'):
            issues.append(_issue(record, "latex.jsonish_text_wrapper", "high", field, "Found leaked JSON text wrapper"))
        if re.search(r"(?<!\\)(?:\\\\)+\s*$", text, flags=re.MULTILINE):
            issues.append(_issue(record, "latex.text_mode_linebreak", "medium", field, "Suspicious text-mode linebreak"))
    return issues


def check_known_bad_patterns(record: QuestionRecord) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    for field, text in latex_fields(record):
        for pattern in KNOWN_BAD_PATTERNS:
            match = pattern.search(text)
            if match:
                issues.append(
                    _issue(
                        record,
                        "content.unrelated_amm_page_material",
                        "high",
                        field,
                        "Field contains AMM page/header/submission material unrelated to the question",
                        _excerpt(text, match.start()),
                    )
                )
                break
    return issues


def check_content_completeness(record: QuestionRecord) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    stem_parts = set(MULTIPART_RE.findall(record.stem_latex))
    solution_text = "\n".join([record.solution_latex, record.explanation_latex])
    solution_parts = set(MULTIPART_RE.findall(solution_text))
    if len(stem_parts) >= 2 and solution_parts and not stem_parts.issubset(solution_parts):
        issues.append(
            _issue(
                record,
                "content.multipart_solution_mismatch",
                "high",
                "solution_latex",
                "Solution does not appear to cover all labeled parts in the stem",
                {"stem_parts": sorted(stem_parts), "solution_parts": sorted(solution_parts)},
            )
        )
    elif len(stem_parts) >= 2 and len(solution_text.strip()) < 160:
        issues.append(
            _issue(
                record,
                "content.multipart_short_solution",
                "medium",
                "solution_latex",
                "Multi-part problem has a very short solution",
                {"stem_parts": sorted(stem_parts), "solution_length": len(solution_text.strip())},
            )
        )
    if re.search(r"(如下图|see the figure|shown in the figure)", record.stem_latex, flags=re.IGNORECASE):
        combined = "\n".join(text for _, text in latex_fields(record))
        if "tikzpicture" not in combined and "includegraphics" not in combined:
            issues.append(_issue(record, "content.missing_figure_asset", "medium", "stem_latex", "Stem refers to a figure but no figure asset is present"))
    return issues


def check_review_state(record: QuestionRecord) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    if record.review_flag == "clean_required":
        issues.append(_issue(record, "review.clean_required", "high", "metadata.curation.review_flag", "Record is marked clean_required"))
    elif record.review_flag == "needs_review":
        issues.append(_issue(record, "review.needs_review", "medium", "metadata.curation.review_flag", "Record is marked needs_review"))
    if record.status == "machine_draft":
        issues.append(_issue(record, "review.machine_draft_status", "low", "status", "Record is still machine_draft"))
    return issues


def latex_fields(record: QuestionRecord) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = [
        ("stem_latex", record.stem_latex),
        ("explanation_latex", record.explanation_latex),
        ("solution_latex", record.solution_latex),
    ]
    for index, choice in enumerate(record.choices):
        fields.append((f"choices[{index}].text_latex", str(choice.get("text_latex", ""))))
    for index, answer in enumerate(record.answers):
        fields.append((f"answers[{index}].latex", str(answer.get("latex", ""))))
    return [(field, text) for field, text in fields if text]


def _environment_issues(text: str) -> tuple[list[str], list[str]]:
    stack: List[str] = []
    unexpected: List[str] = []
    for match in LATEX_ENV_RE.finditer(text):
        action, env = match.group(1), match.group(2)
        if action == "begin":
            stack.append(env)
        elif stack and stack[-1] == env:
            stack.pop()
        else:
            unexpected.append(env)
    return stack, unexpected


def _unescaped_dollar_count(text: str) -> int:
    return len(re.findall(r"(?<!\\)\$", text.replace("$$", "")))


def _excerpt(text: str, start: int, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), start + radius)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def _issue(
    record: QuestionRecord,
    issue_id: str,
    severity: str,
    field: str,
    message: str,
    evidence: object = "",
) -> QualityIssue:
    source_line = record.source_metadata.get("line")
    return QualityIssue(
        id=issue_id,
        severity=severity,
        question_id=record.id,
        field=field,
        message=message,
        evidence=evidence,
        source_path=record.source_path,
        source_line=source_line if isinstance(source_line, int) else None,
    )
```

- [ ] **Step 4: Run checker tests**

Run:

```bash
python3 -m pytest tests/test_quality_checks.py -q
```

Expected: PASS, 9 tests.

- [ ] **Step 5: Run existing related tests**

Run:

```bash
python3 -m pytest tests/test_audit_amm_training_bank.py tests/test_question_loader.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add tools/quality_checks.py tests/test_quality_checks.py
git commit -m "Add deterministic quality checks"
```

---

### Task 3: Render Checker With Cache And Fake-Runner Tests

**Files:**
- Create: `tools/quality_render.py`
- Test: `tests/test_quality_render.py`

**Interfaces:**
- Consumes: `QuestionRecord`, `QualityIssue`, and `SEVERITY_ORDER` from `quality_core.py`.
- Consumes: `latex_fields(record)` from `quality_checks.py`.
- Produces: `RenderOptions` dataclass.
- Produces: `RenderResult` dataclass.
- Produces: `build_render_document(record: QuestionRecord) -> str`.
- Produces: `render_cache_key(record: QuestionRecord, document: str) -> str`.
- Produces: `select_records_for_render(records: list[QuestionRecord], issues: list[QualityIssue], mode: str, sample_size: int) -> list[QuestionRecord]`.
- Produces: `run_render_checks(records: list[QuestionRecord], existing_issues: list[QualityIssue], options: RenderOptions, runner: Callable[..., Any] | None = None, which: Callable[[str], str | None] | None = None) -> list[QualityIssue]`.

- [ ] **Step 1: Write failing render tests**

Create `tests/test_quality_render.py`:

```python
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def record(question_id="q1", **overrides):
    from quality_core import QuestionRecord

    base = {
        "id": question_id,
        "source_path": Path(f"{question_id}.yaml"),
        "source_metadata": {"file": "source.tex"},
        "schema_version": 1,
        "status": "draft",
        "type": "solution",
        "stem_latex": "Compute $1+1$.",
        "solution_latex": "$2$",
    }
    base.update(overrides)
    return QuestionRecord(**base)


def test_build_render_document_contains_fields_and_preamble():
    from quality_render import build_render_document

    doc = build_render_document(
        record(
            type="choice",
            choices=[{"key": "opt1", "text_latex": "$1$", "correct": True}],
            explanation_latex="Explanation $x$.",
        )
    )

    assert r"\usepackage[fontset=fandol]{ctex}" in doc
    assert r"\begin{document}" in doc
    assert "Compute $1+1$." in doc
    assert "$1$" in doc
    assert "Explanation $x$." in doc


def test_render_cache_key_changes_when_content_changes():
    from quality_render import build_render_document, render_cache_key

    left = build_render_document(record(stem_latex="Compute $1+1$."))
    right = build_render_document(record(stem_latex="Compute $1+2$."))

    assert render_cache_key(record(), left) != render_cache_key(record(), right)


def test_select_records_for_render_modes():
    from quality_core import QualityIssue
    from quality_render import select_records_for_render

    records = [record("q1"), record("q2"), record("q3")]
    issues = [QualityIssue(id="review.clean_required", severity="high", question_id="q2")]

    assert select_records_for_render(records, issues, "off", 2) == []
    assert [item.id for item in select_records_for_render(records, issues, "sample", 1)] == ["q1", "q2"]
    assert [item.id for item in select_records_for_render(records, issues, "full", 1)] == ["q1", "q2", "q3"]


def test_run_render_checks_reports_missing_xelatex(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    issues = run_render_checks(
        [record("q1")],
        [],
        RenderOptions(mode="full", output_dir=tmp_path),
        which=lambda name: None,
    )

    assert issues[0].id == "render.missing_xelatex"
    assert issues[0].severity == "critical"


def test_run_render_checks_reports_failed_compile_with_artifacts(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    def fake_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="! Undefined control sequence.", stderr="")

    issues = run_render_checks(
        [record("q1", stem_latex=r"Bad \unknownmacro")],
        [],
        RenderOptions(mode="full", output_dir=tmp_path, keep_workdir=True),
        runner=fake_runner,
        which=lambda name: "/usr/bin/xelatex",
    )

    assert issues[0].id == "render.compile_failed"
    assert issues[0].severity == "critical"
    assert "Undefined control sequence" in issues[0].message
    assert issues[0].render_artifacts["tex"].exists()


def test_run_render_checks_uses_cache_after_success(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    calls = {"count": 0}

    def fake_runner(*args, **kwargs):
        calls["count"] += 1
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    options = RenderOptions(mode="full", output_dir=tmp_path)
    first = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")
    second = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")

    assert first == []
    assert second == []
    assert calls["count"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_quality_render.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'quality_render'`.

- [ ] **Step 3: Implement render checker**

Create `tools/quality_render.py`:

```python
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
    parent = options.output_dir / "quality_render_work" if options.keep_workdir else Path(tempfile.mkdtemp(prefix="quality-render-"))
    parent.mkdir(parents=True, exist_ok=True)
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
    except subprocess.TimeoutExpired as exc:
        return RenderResult(False, 124, f"xelatex timed out after {options.timeout_seconds}s", tex_path if options.keep_workdir else None, None)
    log_path = parent / f"{tex_path.stem}.log"
    output = "\n".join([str(getattr(completed, "stdout", "")), str(getattr(completed, "stderr", ""))]).strip()
    excerpt = _log_excerpt(output)
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
```

- [ ] **Step 4: Run render tests**

Run:

```bash
python3 -m pytest tests/test_quality_render.py -q
```

Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/quality_render.py tests/test_quality_render.py
git commit -m "Add quality audit render checks"
```

---

### Task 4: Report Writers And Summary

**Files:**
- Create: `tools/quality_reports.py`
- Test: `tests/test_quality_reports.py`

**Interfaces:**
- Consumes: `QualityIssue`, `QuestionRecord`, `issue_dict`, and `SEVERITY_ORDER` from `quality_core.py`.
- Produces: `build_summary(records: list[QuestionRecord], issues: list[QualityIssue]) -> dict[str, Any]`.
- Produces: `write_reports(records: list[QuestionRecord], issues: list[QualityIssue], output_dir: Path, metadata: dict[str, Any]) -> dict[str, Path]`.
- Produces files named `quality_audit.json`, `quality_audit.jsonl`, and `quality_audit.html`.

- [ ] **Step 1: Write failing report tests**

Create `tests/test_quality_reports.py`:

```python
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def record(question_id="q1", review_flag="auto_ok"):
    from quality_core import QuestionRecord

    return QuestionRecord(
        id=question_id,
        source_path=Path(f"{question_id}.yaml"),
        source_metadata={"file": "source.tex"},
        schema_version=1,
        status="draft",
        type="solution",
        stem_latex="Stem",
        metadata={"curation": {"review_flag": review_flag}},
    )


def issue(question_id="q1", severity="high"):
    from quality_core import QualityIssue

    return QualityIssue(
        id="review.clean_required",
        severity=severity,
        question_id=question_id,
        field="metadata.curation.review_flag",
        message="Record is marked clean_required",
        evidence={"review_flag": "clean_required"},
        source_path=Path(f"{question_id}.yaml"),
    )


def test_build_summary_counts_severity_and_issue_ids():
    from quality_reports import build_summary

    summary = build_summary([record("q1", "clean_required"), record("q2", "needs_review")], [issue("q1", "high")])

    assert summary["record_count"] == 2
    assert summary["severity_counts"]["high"] == 1
    assert summary["issue_counts"]["review.clean_required"] == 1
    assert summary["review_flag_counts"] == {"clean_required": 1, "needs_review": 1}


def test_write_reports_writes_json_jsonl_and_html(tmp_path):
    from quality_reports import write_reports

    paths = write_reports(
        [record("q1", "clean_required")],
        [issue("q1", "high")],
        tmp_path,
        {"source": "tmp-bank", "render_mode": "off"},
    )

    assert paths["json"].name == "quality_audit.json"
    assert paths["jsonl"].name == "quality_audit.jsonl"
    assert paths["html"].name == "quality_audit.html"

    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["metadata"]["source"] == "tmp-bank"
    assert data["summary"]["severity_counts"]["high"] == 1

    lines = paths["jsonl"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["question_id"] == "q1"

    html = paths["html"].read_text(encoding="utf-8")
    assert "Question Quality Audit" in html
    assert "review.clean_required" in html
    assert "q1" in html
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_quality_reports.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'quality_reports'`.

- [ ] **Step 3: Implement reporters**

Create `tools/quality_reports.py`:

```python
#!/usr/bin/env python3
"""Report writers for question quality audits."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List

from quality_core import QualityIssue, QuestionRecord, issue_dict


def build_summary(records: List[QuestionRecord], issues: List[QualityIssue]) -> Dict[str, Any]:
    severity_counts = Counter(issue.severity for issue in issues)
    issue_counts = Counter(issue.id for issue in issues)
    review_flag_counts = Counter(record.review_flag for record in records if record.review_flag)
    status_counts = Counter(record.status for record in records if record.status)
    return {
        "record_count": len(records),
        "issue_count": len(issues),
        "severity_counts": dict(sorted(severity_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "review_flag_counts": dict(sorted(review_flag_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
    }


def write_reports(
    records: List[QuestionRecord],
    issues: List[QualityIssue],
    output_dir: Path,
    metadata: Dict[str, Any],
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    payload = {
        "metadata": normalized_metadata,
        "summary": build_summary(records, issues),
        "issues": [issue_dict(issue) for issue in issues],
    }

    json_path = output_dir / "quality_audit.json"
    jsonl_path = output_dir / "quality_audit.jsonl"
    html_path = output_dir / "quality_audit.html"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    jsonl_path.write_text(
        "".join(json.dumps(issue_dict(issue), ensure_ascii=False) + "\n" for issue in issues),
        encoding="utf-8",
    )
    html_path.write_text(_render_html(payload), encoding="utf-8")
    return {"json": json_path, "jsonl": jsonl_path, "html": html_path}


def _render_html(payload: Dict[str, Any]) -> str:
    summary = payload["summary"]
    issue_cards = "\n".join(_render_issue_card(issue) for issue in payload["issues"])
    severity_buttons = "\n".join(
        f'<button data-filter="{escape(severity)}">{escape(severity)} ({count})</button>'
        for severity, count in summary["severity_counts"].items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Question Quality Audit</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #1f2933; }}
    header {{ max-width: 1100px; margin-bottom: 18px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }}
    .pill {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 9px; background: #f8fafc; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }}
    button {{ border: 1px solid #94a3b8; background: white; border-radius: 6px; padding: 6px 10px; cursor: pointer; }}
    .issue {{ border: 1px solid #d6dee8; border-left-width: 5px; border-radius: 6px; padding: 12px; margin: 10px 0; max-width: 1100px; }}
    .critical {{ border-left-color: #991b1b; }}
    .high {{ border-left-color: #dc2626; }}
    .medium {{ border-left-color: #d97706; }}
    .low {{ border-left-color: #64748b; }}
    .meta {{ color: #52606d; font-size: 0.92rem; }}
    pre {{ white-space: pre-wrap; background: #f8fafc; padding: 8px; border-radius: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Question Quality Audit</h1>
    <div class="summary">
      <span class="pill">Records: {summary["record_count"]}</span>
      <span class="pill">Issues: {summary["issue_count"]}</span>
      <span class="pill">Generated: {escape(str(payload["metadata"].get("generated_at", "")))}</span>
    </div>
    <label for="search">Filter by question id, issue id, severity, or message</label><br>
    <input id="search" type="search" style="width: min(100%, 720px); padding: 8px;">
    <div class="filters">{severity_buttons}</div>
  </header>
  <main id="issues">
    {issue_cards}
  </main>
  <script>
    const search = document.getElementById('search');
    const cards = Array.from(document.querySelectorAll('.issue'));
    function applyFilter(value) {{
      const needle = value.trim().toLowerCase();
      cards.forEach(card => {{
        card.style.display = card.textContent.toLowerCase().includes(needle) ? '' : 'none';
      }});
    }}
    search.addEventListener('input', () => applyFilter(search.value));
    document.querySelectorAll('button[data-filter]').forEach(button => {{
      button.addEventListener('click', () => {{
        search.value = button.dataset.filter;
        applyFilter(search.value);
      }});
    }});
  </script>
</body>
</html>
"""


def _render_issue_card(issue: Dict[str, Any]) -> str:
    evidence = issue.get("evidence", "")
    evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2) if isinstance(evidence, (dict, list)) else str(evidence)
    artifacts = issue.get("render_artifacts", {}) or {}
    artifact_text = "\n".join(f"{key}: {value}" for key, value in artifacts.items())
    artifact_block = f"<pre>{escape(artifact_text)}</pre>" if artifact_text else ""
    severity = escape(str(issue.get("severity", "")))
    return f"""<section class="issue {severity}">
  <h2>{escape(str(issue.get("id", "")))}</h2>
  <div class="meta">
    {severity} | {escape(str(issue.get("question_id", "")))} | {escape(str(issue.get("field", "")))}
  </div>
  <p>{escape(str(issue.get("message", "")))}</p>
  <pre>{escape(evidence_text)}</pre>
  <div class="meta">{escape(str(issue.get("source_path", "")))}</div>
  {artifact_block}
</section>"""
```

- [ ] **Step 4: Run report tests**

Run:

```bash
python3 -m pytest tests/test_quality_reports.py -q
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/quality_reports.py tests/test_quality_reports.py
git commit -m "Add quality audit reports"
```

---

### Task 5: CLI Orchestration

**Files:**
- Create: `tools/quality_audit.py`
- Test: `tests/test_quality_audit_cli.py`

**Interfaces:**
- Consumes:
  - `load_yaml_bank`, `should_fail`, `DEFAULT_BANK`, `DEFAULT_OUTPUT_DIR` from `quality_core.py`.
  - `run_rule_checks` from `quality_checks.py`.
  - `RenderOptions`, `run_render_checks` from `quality_render.py`.
  - `write_reports` from `quality_reports.py`.
- Produces: `parse_args(argv: list[str] | None = None) -> argparse.Namespace`.
- Produces: `run_audit(args: argparse.Namespace) -> int`.
- Produces: `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_quality_audit_cli.py`:

```python
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def write_yaml(path: Path, record: dict) -> None:
    from legacy_yaml_exporter import record_to_yaml

    path.write_text(record_to_yaml(record), encoding="utf-8")


def test_cli_render_off_writes_reports_and_returns_zero_for_clean_bank(tmp_path):
    from quality_audit import main

    bank = tmp_path / "bank"
    output = tmp_path / "analysis"
    bank.mkdir()
    write_yaml(
        bank / "q001.yaml",
        {
            "schema_version": 1,
            "id": "imported.demo.q001",
            "status": "draft",
            "type": "solution",
            "source": {"file": "examples/demo.tex"},
            "stem_latex": "Compute $1+1$.",
            "solution_latex": "$2$",
            "metadata": {"curation": {"review_flag": "auto_ok"}},
        },
    )

    code = main(["--bank", str(bank), "--output-dir", str(output), "--render-mode", "off"])

    assert code == 0
    assert (output / "quality_audit.json").exists()
    assert (output / "quality_audit.jsonl").exists()
    assert (output / "quality_audit.html").exists()
    data = json.loads((output / "quality_audit.json").read_text(encoding="utf-8"))
    assert data["summary"]["record_count"] == 1
    assert data["summary"]["issue_count"] == 0


def test_cli_returns_one_for_high_issue(tmp_path):
    from quality_audit import main

    bank = tmp_path / "bank"
    output = tmp_path / "analysis"
    bank.mkdir()
    write_yaml(
        bank / "q001.yaml",
        {
            "schema_version": 1,
            "id": "imported.demo.q001",
            "status": "machine_draft",
            "type": "solution",
            "source": {"file": "examples/demo.tex"},
            "stem_latex": "Compute $1+1$.",
            "solution_latex": "$2$",
            "metadata": {"curation": {"review_flag": "clean_required"}},
        },
    )

    code = main(["--bank", str(bank), "--output-dir", str(output), "--render-mode", "off"])

    assert code == 1
    jsonl = (output / "quality_audit.jsonl").read_text(encoding="utf-8")
    assert "review.clean_required" in jsonl


def test_cli_question_id_filter_audits_only_selected_record(tmp_path):
    from quality_audit import main

    bank = tmp_path / "bank"
    output = tmp_path / "analysis"
    bank.mkdir()
    for index in (1, 2):
        write_yaml(
            bank / f"q{index:03d}.yaml",
            {
                "schema_version": 1,
                "id": f"imported.demo.q{index:03d}",
                "status": "draft",
                "type": "solution",
                "source": {"file": "examples/demo.tex"},
                "stem_latex": f"Compute ${index}+1$.",
                "solution_latex": "$2$",
            },
        )

    code = main(
        [
            "--bank",
            str(bank),
            "--output-dir",
            str(output),
            "--render-mode",
            "off",
            "--question-id",
            "imported.demo.q002",
        ]
    )

    assert code == 0
    data = json.loads((output / "quality_audit.json").read_text(encoding="utf-8"))
    assert data["summary"]["record_count"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_quality_audit_cli.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'quality_audit'`.

- [ ] **Step 3: Implement CLI**

Create `tools/quality_audit.py`:

```python
#!/usr/bin/env python3
"""Run publication-quality audits for structured question banks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from quality_checks import run_rule_checks
from quality_core import DEFAULT_BANK, DEFAULT_OUTPUT_DIR, QuestionRecord, load_yaml_bank, should_fail
from quality_render import RenderOptions, run_render_checks
from quality_reports import write_reports


VALID_RENDER_MODES = ("off", "sample", "full")
VALID_SEVERITIES = ("low", "medium", "high", "critical")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit mathematical question-bank quality.")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK, help=f"YAML question directory (default: {DEFAULT_BANK})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Report output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--render-mode", choices=VALID_RENDER_MODES, default="sample")
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument("--fail-on", choices=VALID_SEVERITIES, default="high")
    parser.add_argument("--include-status", action="append", default=[])
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--keep-render-workdir", action="store_true")
    return parser.parse_args(argv)


def run_audit(args: argparse.Namespace) -> int:
    records, source_issues = load_yaml_bank(args.bank)
    records = _filter_records(records, args.include_status, args.question_id)

    rule_issues = run_rule_checks(records)
    render_issues = run_render_checks(
        records,
        source_issues + rule_issues,
        RenderOptions(
            mode=args.render_mode,
            output_dir=args.output_dir,
            sample_size=args.sample_size,
            keep_workdir=args.keep_render_workdir,
        ),
    )
    issues = source_issues + rule_issues + render_issues

    report_paths = write_reports(
        records,
        issues,
        args.output_dir,
        {
            "source": str(args.bank),
            "render_mode": args.render_mode,
            "sample_size": args.sample_size,
            "fail_on": args.fail_on,
        },
    )
    _print_summary(records, issues, report_paths)
    return 1 if should_fail(issues, args.fail_on) else 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    return run_audit(args)


def _filter_records(
    records: List[QuestionRecord],
    statuses: List[str],
    question_ids: List[str],
) -> List[QuestionRecord]:
    selected = records
    if statuses:
        allowed_statuses = set(statuses)
        selected = [record for record in selected if record.status in allowed_statuses]
    if question_ids:
        allowed_ids = set(question_ids)
        selected = [record for record in selected if record.id in allowed_ids]
    return selected


def _print_summary(records, issues, report_paths) -> None:
    counts = {}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    print(f"records: {len(records)}")
    print(f"issues: {len(issues)}")
    for severity in ("critical", "high", "medium", "low"):
        print(f"{severity}: {counts.get(severity, 0)}")
    print(f"json: {report_paths['json']}")
    print(f"jsonl: {report_paths['jsonl']}")
    print(f"html: {report_paths['html']}")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python3 -m pytest tests/test_quality_audit_cli.py -q
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Run all quality-audit tests**

Run:

```bash
python3 -m pytest \
  tests/test_quality_core.py \
  tests/test_quality_checks.py \
  tests/test_quality_render.py \
  tests/test_quality_reports.py \
  tests/test_quality_audit_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add tools/quality_audit.py tests/test_quality_audit_cli.py
git commit -m "Add quality audit CLI"
```

---

### Task 6: Repository-Level Verification And AMM Smoke Run

**Files:**
- Modify only if required by test failures:
  - `tools/quality_core.py`
  - `tools/quality_checks.py`
  - `tools/quality_render.py`
  - `tools/quality_reports.py`
  - `tools/quality_audit.py`
- No new tests unless a regression is found during verification.

**Interfaces:**
- Consumes the complete CLI from Task 5.
- Produces verified reports in `analysis/` when run on the real AMM bank.

- [ ] **Step 1: Run the focused quality test suite**

Run:

```bash
python3 -m pytest \
  tests/test_quality_core.py \
  tests/test_quality_checks.py \
  tests/test_quality_render.py \
  tests/test_quality_reports.py \
  tests/test_quality_audit_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run existing related tests**

Run:

```bash
python3 -m pytest \
  tests/test_question_loader.py \
  tests/test_audit_amm_training_bank.py \
  tests/test_build_static_amm_site.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run the full test suite**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS. If unrelated pre-existing failures appear, record the exact failing tests and do not change unrelated code.

- [ ] **Step 4: Run quality audit against the real AMM bank without render**

Run:

```bash
python3 tools/quality_audit.py --render-mode off
```

Expected:

- Reports are written to `analysis/quality_audit.json`, `analysis/quality_audit.jsonl`, and `analysis/quality_audit.html`.
- The command likely exits `1` because current AMM records include `review_flag=clean_required`, which is intentionally `high`.
- The printed summary lists nonzero issue counts.

If the command exits `1`, rerun this inspection command to confirm the reason is expected high-risk issues:

```bash
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("analysis/quality_audit.json").read_text(encoding="utf-8"))
print(data["summary"]["severity_counts"])
print(data["summary"]["issue_counts"].get("review.clean_required", 0))
PY
```

Expected: `review.clean_required` count is greater than `0`.

- [ ] **Step 5: Run one fake-free real render smoke if xelatex exists**

Run:

```bash
if command -v xelatex >/dev/null 2>&1; then
  python3 tools/quality_audit.py \
    --render-mode full \
    --question-id imported.amm_analysis_training_full_zh.p10337 \
    --keep-render-workdir || true
else
  echo "xelatex not available; skipping manual render smoke"
fi
```

Expected:

- If `xelatex` exists, render artifacts and reports are generated.
- The command may return nonzero for legitimate quality issues on `p10337`.
- If `xelatex` does not exist, the script prints the skip message.

- [ ] **Step 6: Commit verification fixes or record no-op**

If verification required code fixes, run:

```bash
git add tools/quality_core.py tools/quality_checks.py tools/quality_render.py tools/quality_reports.py tools/quality_audit.py tests/test_quality_core.py tests/test_quality_checks.py tests/test_quality_render.py tests/test_quality_reports.py tests/test_quality_audit_cli.py
git commit -m "Verify quality audit toolchain"
```

If no files changed, do not create an empty commit. Record the verification commands and outcomes in the final implementation response.

---

## Plan Self-Review

Spec coverage:

- YAML bank loading and normalization: Task 1.
- Rule-based structure, schema, LaTeX text, and content-risk checks: Task 2.
- Optional LaTeX rendering checks through `xelatex`: Task 3.
- Render cache by content hash: Task 3.
- JSON, JSONL, and HTML reports: Task 4.
- Soft-gate exit behavior: Task 1 and Task 5.
- CLI options and defaults: Task 5.
- Normal tests avoiding TeX dependency: Task 3 uses fake runner and Task 6 keeps real render as conditional smoke.
- AMM real-bank verification: Task 6.
- Future `.tex` adapter path: file structure and stable `QuestionRecord` interface in Task 1.

Placeholder scan:

- The plan contains no incomplete markers. Every code step includes concrete files, functions, commands, and expected outcomes.

Type consistency:

- `QuestionRecord`, `QualityIssue`, `RenderOptions`, `run_rule_checks`, `run_render_checks`, and `write_reports` signatures are defined before use.
- CLI and reporter tasks consume the same names produced by earlier tasks.
