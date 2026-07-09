import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def record(question_id="q1", review_flag="auto_ok", **overrides):
    from quality_core import QuestionRecord

    base = {
        "id": question_id,
        "source_path": Path(f"{question_id}.yaml"),
        "source_metadata": {"file": "source.tex", "preview_url": f"http://127.0.0.1:8000/source/{question_id}"},
        "schema_version": 1,
        "status": "draft",
        "type": "solution",
        "stem_latex": "Stem",
        "metadata": {"curation": {"review_flag": review_flag}},
    }
    base.update(overrides)
    return QuestionRecord(**base)


def issue(question_id="q1", severity="high", issue_id="review.clean_required", **overrides):
    from quality_core import QualityIssue

    base = {
        "id": issue_id,
        "severity": severity,
        "question_id": question_id,
        "field": "metadata.curation.review_flag",
        "message": "Record is marked clean_required",
        "evidence": {"review_flag": "clean_required"},
        "source_path": Path(f"{question_id}.yaml"),
    }
    base.update(overrides)
    return QualityIssue(**base)


def test_build_summary_counts_severity_source_and_issue_ids():
    from quality_reports import build_summary

    records = [
        record("q1", "clean_required", source_metadata={"file": "source-a.tex"}, source_path=Path("bank/a/q1.yaml")),
        record(
            "q2",
            "needs_review",
            source_metadata={"translation_of": "translated-source.tex"},
            source_path=Path("bank/b/q2.yaml"),
        ),
        record("q3", "auto_ok", source_metadata={"note": "no explicit source"}, source_path=Path("bank/c/q3.yaml")),
    ]
    issues = [
        issue("q1", "high", issue_id="review.clean_required"),
        issue("q2", "critical", issue_id="render.compile_failed"),
        issue("q3", "low", issue_id="review.needs_review"),
    ]

    summary = build_summary(records, issues)

    assert summary["record_count"] == 3
    assert summary["issue_count"] == 3
    assert list(summary["severity_counts"]) == ["critical", "high", "low"]
    assert summary["severity_counts"] == {"critical": 1, "high": 1, "low": 1}
    assert summary["issue_counts"] == {
        "render.compile_failed": 1,
        "review.clean_required": 1,
        "review.needs_review": 1,
    }
    assert summary["review_flag_counts"] == {
        "auto_ok": 1,
        "clean_required": 1,
        "needs_review": 1,
    }
    assert summary["source_counts"] == {
        "bank/c/q3.yaml": 1,
        "source-a.tex": 1,
        "translated-source.tex": 1,
    }


def test_write_reports_writes_json_jsonl_and_html_with_required_affordances(tmp_path):
    from quality_reports import write_reports

    records = [
        record(
            "q1",
            "clean_required",
            source_metadata={"file": "source-a.tex", "preview_url": "http://127.0.0.1:8000/source/q1"},
            source_path=Path("bank/a/q1.yaml"),
        ),
        record(
            "q2",
            "needs_review",
            source_metadata={"translation_of": "translated-source.tex"},
            source_path=Path("bank/b/q2.yaml"),
        ),
    ]
    issues = [
        issue("q1", "high", issue_id="review.clean_required"),
        issue(
            "q1",
            "critical",
            issue_id="render.compile_failed",
            evidence={"log_excerpt": "Undefined control sequence."},
            render_artifacts={"log": Path("/tmp/render/q1.log"), "tex": Path("/tmp/render/q1.tex")},
        ),
        issue("q2", "medium", issue_id="review.needs_review"),
    ]

    paths = write_reports(
        records,
        issues,
        tmp_path,
        {"source": "tmp-bank", "render_mode": "off"},
    )

    assert paths["json"].name == "quality_audit.json"
    assert paths["jsonl"].name == "quality_audit.jsonl"
    assert paths["html"].name == "quality_audit.html"

    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["metadata"]["source"] == "tmp-bank"
    assert data["summary"]["severity_counts"] == {"critical": 1, "high": 1, "medium": 1}
    assert data["summary"]["source_counts"] == {
        "source-a.tex": 1,
        "translated-source.tex": 1,
    }

    lines = paths["jsonl"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["question_id"] == "q1"

    html = paths["html"].read_text(encoding="utf-8")
    assert "Question Quality Audit" in html
    assert 'data-filter-kind="severity"' in html
    assert 'data-filter-kind="issue-id"' in html
    assert 'data-filter-kind="review-flag"' in html
    assert 'data-question-id="q1"' in html
    assert 'data-question-id="q2"' in html
    assert "http://127.0.0.1:8000/source/q1" in html
    assert "Undefined control sequence." in html
    assert "/tmp/render/q1.log" in html
    assert "/tmp/render/q1.tex" in html
    assert "render.compile_failed" in html
    assert "review.clean_required" in html
    assert "review.needs_review" in html
