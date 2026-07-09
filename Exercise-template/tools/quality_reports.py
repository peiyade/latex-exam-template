#!/usr/bin/env python3
"""Report writers for question quality audits."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List

from quality_core import QualityIssue, QuestionRecord, SEVERITY_ORDER, issue_dict


def build_summary(records: List[QuestionRecord], issues: List[QualityIssue]) -> Dict[str, Any]:
    severity_counts = Counter(issue.severity for issue in issues)
    issue_counts = Counter(issue.id for issue in issues)
    review_flag_counts = Counter(record.review_flag for record in records if record.review_flag)
    status_counts = Counter(record.status for record in records if record.status)
    source_counts = Counter()
    for record in records:
        source_key = _source_count_key(record)
        if source_key:
            source_counts[source_key] += 1

    ordered_severity_counts = {
        severity: severity_counts[severity]
        for severity in sorted(SEVERITY_ORDER, key=SEVERITY_ORDER.get, reverse=True)
        if severity_counts[severity]
    }

    return {
        "record_count": len(records),
        "issue_count": len(issues),
        "severity_counts": ordered_severity_counts,
        "issue_counts": dict(sorted(issue_counts.items())),
        "review_flag_counts": dict(sorted(review_flag_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
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
    html_path.write_text(_render_html(records, payload), encoding="utf-8")
    return {"json": json_path, "jsonl": jsonl_path, "html": html_path}


def _source_count_key(record: QuestionRecord) -> str:
    source = record.source_metadata if isinstance(record.source_metadata, dict) else {}
    for key in ("file", "translation_of"):
        value = source.get(key)
        if value:
            return str(value)
    fallback = record.source_path.parent / record.source_path.name
    return str(fallback)


def _source_display_label(record: QuestionRecord) -> str:
    source = record.source_metadata if isinstance(record.source_metadata, dict) else {}
    for key in ("file", "translation_of"):
        value = source.get(key)
        if value:
            return str(value)
    return _source_count_key(record)


def _render_html(records: List[QuestionRecord], payload: Dict[str, Any]) -> str:
    summary = payload["summary"]
    records_by_id = {record.id: record for record in records if record.id}
    question_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for issue in payload["issues"]:
        question_groups[str(issue.get("question_id", "")) or "(unassigned)"].append(issue)

    question_sections = "\n".join(
        _render_question_group(question_id, question_groups[question_id], records_by_id.get(question_id))
        for question_id in sorted(question_groups)
    )

    severity_buttons = _render_filter_buttons(
        "severity",
        "Severity",
        summary["severity_counts"],
        ["critical", "high", "medium", "low"],
    )
    issue_buttons = _render_filter_buttons("issue-id", "Issue ID", summary["issue_counts"])
    review_buttons = _render_filter_buttons("review-flag", "Review Flag", summary["review_flag_counts"])

    source_lines = "".join(
        f"<li><code>{escape(source)}</code>: {count}</li>" for source, count in summary["source_counts"].items()
    )
    source_summary = f"<ul class=\"source-counts\">{source_lines}</ul>" if source_lines else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Question Quality Audit</title>
  <style>
    :root {{
      color-scheme: light;
      --border: #cbd5e1;
      --text: #1f2937;
      --muted: #52606d;
      --panel: #f8fafc;
      --chip: #ffffff;
      --chip-border: #94a3b8;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 24px;
      color: var(--text);
      background: #fff;
    }}
    header {{
      max-width: 1180px;
      margin-bottom: 20px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 16px 0;
    }}
    .pill {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 10px;
      background: var(--panel);
    }}
    .filters {{
      display: grid;
      gap: 12px;
      margin: 16px 0 12px;
    }}
    .filter-group {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .filter-label {{
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--muted);
      min-width: 92px;
    }}
    button.filter-button {{
      border: 1px solid var(--chip-border);
      background: var(--chip);
      border-radius: 6px;
      padding: 6px 10px;
      cursor: pointer;
    }}
    button.filter-button[aria-pressed="true"] {{
      background: #1d4ed8;
      color: white;
      border-color: #1d4ed8;
    }}
    .search-row {{
      margin-top: 10px;
    }}
    .search-row input {{
      width: min(100%, 720px);
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
    }}
    .source-counts {{
      margin: 10px 0 0;
      padding-left: 20px;
      color: var(--muted);
    }}
    .question-group {{
      border: 1px solid #d6dee8;
      border-radius: 8px;
      margin: 14px 0;
      padding: 14px;
      max-width: 1180px;
    }}
    .question-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .question-title {{
      margin: 0;
      font-size: 1.05rem;
    }}
    .question-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 8px;
      background: #f8fafc;
    }}
    .question-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      color: var(--muted);
    }}
    .issue-list {{
      display: grid;
      gap: 10px;
    }}
    .issue-card {{
      border: 1px solid #d6dee8;
      border-left-width: 5px;
      border-radius: 6px;
      padding: 12px;
      background: white;
    }}
    .issue-card[data-severity="critical"] {{ border-left-color: #991b1b; }}
    .issue-card[data-severity="high"] {{ border-left-color: #dc2626; }}
    .issue-card[data-severity="medium"] {{ border-left-color: #d97706; }}
    .issue-card[data-severity="low"] {{ border-left-color: #64748b; }}
    .issue-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 8px;
      align-items: baseline;
      margin-bottom: 8px;
    }}
    .issue-id {{
      margin: 0;
      font-size: 0.98rem;
    }}
    .issue-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .issue-message {{
      margin: 8px 0;
    }}
    .detail-block {{
      margin-top: 10px;
    }}
    .detail-block h4 {{
      margin: 0 0 6px;
      font-size: 0.88rem;
      color: var(--muted);
    }}
    pre {{
      white-space: pre-wrap;
      background: var(--panel);
      padding: 8px;
      border-radius: 4px;
      margin: 0;
      overflow-x: auto;
    }}
    ul {{
      margin: 0;
    }}
    code {{
      font-size: 0.92em;
    }}
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
    {source_summary}
    <div class="filters">
      {severity_buttons}
      {issue_buttons}
      {review_buttons}
    </div>
    <div class="search-row">
      <label for="search">Search across question, issue, or evidence text</label><br>
      <input id="search" type="search" autocomplete="off">
    </div>
  </header>
  <main id="questions">
    {question_sections}
  </main>
  <script>
    const state = {{
      severity: "",
      issueId: "",
      reviewFlag: "",
      search: "",
    }};

    const groups = Array.from(document.querySelectorAll(".question-group"));
    const buttons = Array.from(document.querySelectorAll("button.filter-button"));
    const search = document.getElementById("search");

    function setPressed(kind, value) {{
      buttons.forEach((button) => {{
        if (button.dataset.filterKind === kind) {{
          button.setAttribute("aria-pressed", button.dataset.filterValue === value ? "true" : "false");
        }}
      }});
    }}

    function applyFilters() {{
      const needle = state.search.trim().toLowerCase();
      groups.forEach((group) => {{
        const groupReviewOk = !state.reviewFlag || group.dataset.reviewFlag === state.reviewFlag;
        let visibleIssueCount = 0;
        group.querySelectorAll(".issue-card").forEach((card) => {{
          const issueOk = (!state.severity || card.dataset.severity === state.severity)
            && (!state.issueId || card.dataset.issueId === state.issueId)
            && (!needle || card.dataset.searchText.includes(needle) || group.dataset.searchText.includes(needle));
          card.hidden = !issueOk;
          if (issueOk) {{
            visibleIssueCount += 1;
          }}
        }});
        group.hidden = !groupReviewOk || visibleIssueCount === 0;
      }});
    }}

    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const kind = button.dataset.filterKind;
        const value = button.dataset.filterValue || "";
        if (kind === "severity") {{
          state.severity = value;
        }} else if (kind === "issue-id") {{
          state.issueId = value;
        }} else if (kind === "review-flag") {{
          state.reviewFlag = value;
        }}
        setPressed(kind, value);
        applyFilters();
      }});
    }});

    search.addEventListener("input", () => {{
      state.search = search.value;
      applyFilters();
    }});

    applyFilters();
  </script>
</body>
</html>
"""


def _render_filter_buttons(kind: str, label: str, counts: Dict[str, int], preferred_order: Iterable[str] | None = None) -> str:
    ordered_items = []
    seen = set()
    if preferred_order is not None:
        for key in preferred_order:
            if key in counts:
                ordered_items.append((key, counts[key]))
                seen.add(key)
    for key in sorted(counts):
        if key not in seen:
            ordered_items.append((key, counts[key]))

    buttons = [
        f'<button type="button" class="filter-button" data-filter-kind="{escape(kind)}" data-filter-value="" aria-pressed="true">All {escape(label.lower())}</button>'
    ]
    buttons.extend(
        f'<button type="button" class="filter-button" data-filter-kind="{escape(kind)}" data-filter-value="{escape(value)}" aria-pressed="false">{escape(value)} ({count})</button>'
        for value, count in ordered_items
    )
    return f'<div class="filter-group" data-filter-group="{escape(kind)}"><span class="filter-label">{escape(label)}</span>{"".join(buttons)}</div>'


def _render_question_group(question_id: str, issues: List[Dict[str, Any]], record: QuestionRecord | None) -> str:
    review_flag = record.review_flag if record else ""
    source_label = _source_display_label(record) if record else ""
    status = record.status if record else ""
    preview_url = ""
    if record and isinstance(record.source_metadata, dict):
        preview_url = str(record.source_metadata.get("preview_url", "") or "")

    meta_bits = []
    if source_label:
        meta_bits.append(f'<span class="badge">Source: {escape(source_label)}</span>')
    if review_flag:
        meta_bits.append(f'<span class="badge">Review: {escape(review_flag)}</span>')
    if status:
        meta_bits.append(f'<span class="badge">Status: {escape(status)}</span>')

    preview_link = (
        f'<a href="{escape(preview_url)}" target="_blank" rel="noreferrer">Local preview</a>' if preview_url else ""
    )
    question_search_text = " ".join(
        [
            question_id,
            source_label,
            review_flag,
            status,
            preview_url,
            " ".join(str(issue.get("id", "")) for issue in issues),
            " ".join(str(issue.get("message", "")) for issue in issues),
            " ".join(str(issue.get("field", "")) for issue in issues),
        ]
    ).lower()
    issue_cards = "\n".join(_render_issue_card(issue) for issue in issues)
    return f"""<section class="question-group" data-question-id="{escape(question_id)}" data-review-flag="{escape(review_flag)}" data-search-text="{escape(question_search_text)}">
  <header class="question-header">
    <div>
      <h2 class="question-title">Question {escape(question_id)}</h2>
      <div class="question-meta">
        {"".join(meta_bits)}
      </div>
    </div>
    <div class="question-links">
      {preview_link}
    </div>
  </header>
  <div class="issue-list">
    {issue_cards}
  </div>
</section>"""


def _render_issue_card(issue: Dict[str, Any]) -> str:
    severity = str(issue.get("severity", ""))
    issue_id = str(issue.get("id", ""))
    question_id = str(issue.get("question_id", ""))
    field = str(issue.get("field", ""))
    message = str(issue.get("message", ""))
    evidence = issue.get("evidence", "")
    render_artifacts = issue.get("render_artifacts", {}) or {}

    evidence_block = ""
    if evidence not in ("", None, {}, []):
        evidence_block = f"""<div class="detail-block">
      <h4>Evidence</h4>
      <pre>{escape(_format_evidence(evidence))}</pre>
    </div>"""

    artifact_block = ""
    if render_artifacts:
        artifact_lines = "\n".join(
            f'<li><code>{escape(str(name))}</code>: <code>{escape(str(path))}</code></li>'
            for name, path in sorted(render_artifacts.items())
        )
        artifact_block = f"""<div class="detail-block">
      <h4>Render artifacts</h4>
      <ul>{artifact_lines}</ul>
    </div>"""

    search_text = " ".join(
        [
            issue_id,
            severity,
            question_id,
            field,
            message,
            _format_evidence(evidence),
            " ".join(f"{name} {path}" for name, path in sorted(render_artifacts.items())),
        ]
    ).lower()

    return f"""<article class="issue-card" data-issue-id="{escape(issue_id)}" data-severity="{escape(severity)}" data-search-text="{escape(search_text)}">
    <div class="issue-head">
      <h3 class="issue-id">{escape(issue_id)}</h3>
      <div class="issue-meta">
        <span class="badge">Severity: {escape(severity)}</span>
        <span class="badge">Question: {escape(question_id)}</span>
        <span class="badge">Field: {escape(field)}</span>
      </div>
    </div>
    <p class="issue-message">{escape(message)}</p>
    {evidence_block}
    {artifact_block}
  </article>"""


def _format_evidence(evidence: Any) -> str:
    if isinstance(evidence, (dict, list)):
        return json.dumps(evidence, ensure_ascii=False, indent=2)
    return str(evidence)
