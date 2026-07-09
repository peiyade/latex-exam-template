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
