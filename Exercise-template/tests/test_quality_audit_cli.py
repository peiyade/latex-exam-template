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
