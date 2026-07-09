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


def test_choice_checker_flags_malformed_choice_entries():
    from quality_checks import check_type_consistency

    issues = check_type_consistency(
        record(
            type="choice",
            choices=["bad-choice", {"key": "opt1", "text_latex": "$1$", "correct": True}],
        )
    )

    assert "type.choice_malformed_choice" in issue_ids(issues)
    assert "type.choice_correct_count" not in issue_ids(issues)


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


def test_fillin_checker_flags_malformed_answer_entries():
    from quality_checks import check_type_consistency

    issues = check_type_consistency(
        record(
            type="fillin",
            stem_latex=r"Answer \blank{blank1}.",
            answers=["bad-answer", {"key": "blank1", "latex": "$1$"}],
        )
    )

    assert "type.fillin_malformed_answer" in issue_ids(issues)


def test_fillin_checker_flags_answers_without_blank_markers():
    from quality_checks import check_type_consistency

    issues = check_type_consistency(
        record(
            type="fillin",
            stem_latex="Answer the question.",
            answers=[{"key": "blank1", "latex": "$1$"}],
        )
    )

    assert issues[0].id == "type.fillin_blank_answer_mismatch"
    assert issues[0].severity == "high"
    assert "blank1" in str(issues[0].evidence)


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


def test_latex_fields_skips_malformed_nested_items():
    from quality_checks import latex_fields

    fields = latex_fields(
        record(
            type="choice",
            choices=["bad-choice", {"key": "opt1", "text_latex": "$1$"}],
            answers=["bad-answer", {"key": "blank1", "latex": "$2$"}],
        )
    )

    assert ("choices[1].text_latex", "$1$") in fields
    assert ("answers[1].latex", "$2$") in fields
    assert all("bad-choice" not in text and "bad-answer" not in text for _, text in fields)


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
