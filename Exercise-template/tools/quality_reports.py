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
