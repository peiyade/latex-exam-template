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
