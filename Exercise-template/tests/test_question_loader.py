import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def write_question(path: Path, question_id: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""schema_version: 1
id: {question_id}
status: draft
type: solution
source:
  file: examples/demo.tex
stem_latex: |-
  {body}
""",
        encoding="utf-8",
    )


def test_load_question_bank_indexes_imported_questions(tmp_path):
    from question_loader import load_question_bank

    write_question(tmp_path / "demo" / "q001.yaml", "imported.demo.q001", "根据导数的定义")
    write_question(tmp_path / "demo" / "q002.yaml", "imported.demo.q002", r"\blank{blank1}")

    bank = load_question_bank(tmp_path)

    assert len(bank.questions) == 2
    question = bank.get("imported.demo.q001")
    assert question["type"] == "solution"
    assert question["stem_latex"].startswith("根据导数的定义")


def test_fillin_question_keeps_semantic_blank_marker(tmp_path):
    from question_loader import load_question_bank

    write_question(tmp_path / "demo" / "q004.yaml", "imported.demo.q004", r"\blank{blank1}")

    bank = load_question_bank(tmp_path)
    question = bank.get("imported.demo.q004")

    assert r"\blank{blank1}" in question["stem_latex"]


def test_list_sources_groups_questions_by_imported_directory(tmp_path):
    from question_loader import load_question_bank

    write_question(tmp_path / "demo" / "q001.yaml", "imported.demo.q001", "One")
    write_question(tmp_path / "demo" / "q002.yaml", "imported.demo.q002", "Two")
    write_question(tmp_path / "other" / "q001.yaml", "imported.other.q001", "Three")

    bank = load_question_bank(tmp_path)
    sources = bank.list_sources()

    demo = next(source for source in sources if source["slug"] == "demo")
    assert demo["count"] == 2
    assert demo["first_question_id"] == "imported.demo.q001"

    other = next(source for source in sources if source["slug"] == "other")
    assert other["count"] == 1
    assert other["first_question_id"] == "imported.other.q001"


def test_yaml_subset_parses_literal_block_sequence_items():
    from question_loader import parse_yaml_subset

    parsed = parse_yaml_subset(
        """
metadata:
  curation:
    data_quality_flags:
      - |-
        题解中有明显 OCR/LaTeX 错误：\\vec{w} 应核对
      - "另一条标记"
"""
    )

    assert parsed["metadata"]["curation"]["data_quality_flags"] == [
        r"题解中有明显 OCR/LaTeX 错误：\vec{w} 应核对",
        "另一条标记",
    ]
