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


def test_normalize_question_converts_null_text_fields_to_empty_strings(tmp_path):
    from quality_core import normalize_question

    normalized = normalize_question(
        {
            "schema_version": 1,
            "id": None,
            "status": None,
            "type": None,
            "stem_latex": None,
            "explanation_latex": None,
            "solution_latex": None,
            "comment": None,
        },
        tmp_path / "q001.yaml",
    )

    assert normalized.id == ""
    assert normalized.status == ""
    assert normalized.type == ""
    assert normalized.stem_latex == ""
    assert normalized.explanation_latex == ""
    assert normalized.solution_latex == ""
    assert normalized.comment == ""


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
