import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def sample_record():
    return {
        "schema_version": 1,
        "id": "imported.amm_analysis_training_full_zh.p12403_2",
        "status": "machine_draft",
        "type": "solution",
        "source": {
            "translation_of": "imported.amm_analysis_training_full_source.p12403_2",
            "legacy_id": "amm#12403",
            "line": 96444,
            "preview_url": "http://127.0.0.1:8000/source/amm_problems_and_solutions?q=imported.amm_problems_and_solutions.p12403_2",
        },
        "stem_latex": "设 $a,b,c$ 为实数。",
        "solution_latex": "由 AM-GM 得证。",
        "comment": "五参数不等式族",
        "metadata": {
            "problem_number": 12403,
            "section_title": "A Family of Five-Parameter Inequalities",
            "curation": {
                "main_domain": "inequality",
                "priority_for_course": "high",
                "review_flag": "needs_review",
                "basic_judgment": "核心题目。",
                "structure_tags": ["五变量不等式", "参数范围"],
                "candidate_methods": ["AM-GM", "Karamata 不等式"],
                "data_quality_flags": ["长公式较多"],
            },
            "training_card": {
                "recognition_cues": ["倒数和", "非负变量"],
                "first_reaction": "先排序。",
                "key_transformation": "排序后做成对平均。",
                "solution_skeleton": ["排序", "AM-HM"],
                "common_traps": ["不要忽略边界"],
                "general_template": "多变量倒数和先找极端结构。",
                "training_use": "高价值不等式训练。",
                "human_notes": "",
            },
            "translation": {
                "model": "manual:codex-reviewed",
                "review_status": "machine_draft",
            },
        },
    }


def test_normalize_question_extracts_site_fields():
    from build_static_amm_site import normalize_question

    normalized = normalize_question(sample_record())

    assert normalized["id"] == "imported.amm_analysis_training_full_zh.p12403_2"
    assert normalized["source_id"] == "imported.amm_analysis_training_full_source.p12403_2"
    assert normalized["problem_number"] == 12403
    assert normalized["title"] == "五参数不等式族"
    assert normalized["domain"] == "inequality"
    assert normalized["priority"] == "high"
    assert normalized["review_flag"] == "needs_review"
    assert normalized["tags"] == ["五变量不等式", "参数范围"]
    assert normalized["methods"] == ["AM-GM", "Karamata 不等式"]
    assert normalized["stem_latex"] == "设 $a,b,c$ 为实数。"
    assert normalized["solution_latex"] == "由 AM-GM 得证。"
    assert normalized["has_tikz"] is False
    assert "五变量不等式" in normalized["search_text"]
    assert "manual:codex-reviewed" in normalized["translation_model"]


def test_normalize_question_detects_tikz():
    from build_static_amm_site import normalize_question

    record = sample_record()
    record["solution_latex"] = "\\begin{tikzpicture}\\draw (0,0)--(1,1);\\end{tikzpicture}"

    assert normalize_question(record)["has_tikz"] is True


def test_compute_stats_counts_domain_priority_review_and_tags():
    from build_static_amm_site import compute_stats, normalize_question

    q1 = normalize_question(sample_record())
    q2 = {
        **q1,
        "id": "q2",
        "domain": "analysis",
        "priority": "medium",
        "review_flag": "auto_ok",
        "tags": ["极限"],
    }

    stats = compute_stats([q1, q2])

    assert stats["total"] == 2
    assert stats["domains"] == {"analysis": 1, "inequality": 1}
    assert stats["priorities"] == {"high": 1, "medium": 1}
    assert stats["review_flags"] == {"auto_ok": 1, "needs_review": 1}
    assert stats["tags"]["五变量不等式"] == 1
    assert stats["tags"]["极限"] == 1


def write_yaml(path, text):
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_validate_audit_rejects_incomplete_bank():
    from build_static_amm_site import validate_audit

    audit = {
        "source_count": 981,
        "translated_count": 980,
        "missing_translation_count": 1,
        "failure_count": 0,
        "format_issues": [],
    }

    try:
        validate_audit(audit)
    except ValueError as exc:
        assert "translated_count" in str(exc) or "missing_translation_count" in str(exc)
    else:
        raise AssertionError("validate_audit should reject incomplete translated bank")


def test_validate_audit_rejects_unresolved_failures_and_format_issues():
    from build_static_amm_site import validate_audit

    audit = {
        "source_count": 981,
        "translated_count": 981,
        "missing_translation_count": 0,
        "failure_count": 1,
        "format_issues": [{"id": "q1", "issue": "text_mode_linebreak"}],
    }

    try:
        validate_audit(audit)
    except ValueError as exc:
        assert "failure_count" in str(exc) or "format_issues" in str(exc)
    else:
        raise AssertionError("validate_audit should reject unresolved failures")


def test_build_site_writes_static_files_and_source_metadata(tmp_path):
    from build_static_amm_site import build_site

    zh_root = tmp_path / "zh"
    source_root = tmp_path / "source"
    output_root = tmp_path / "site"
    zh_root.mkdir()
    source_root.mkdir()

    write_yaml(
        zh_root / "p12403_2.yaml",
        """
schema_version: 1
id: imported.amm_analysis_training_full_zh.p12403_2
status: machine_draft
type: solution
source:
  translation_of: imported.amm_analysis_training_full_source.p12403_2
  legacy_id: amm#12403
stem_latex: |-
  设 $a$ 为实数。
solution_latex: |-
  由 AM-GM 得证。
comment: "五参数不等式族"
metadata:
  problem_number: 12403
  section_title: "A Family of Five-Parameter Inequalities"
  curation:
    main_domain: inequality
    priority_for_course: high
    review_flag: needs_review
    basic_judgment: "核心题目。"
    structure_tags:
      - "五变量不等式"
    candidate_methods:
      - AM-GM
    data_quality_flags: []
  training_card:
    recognition_cues:
      - "倒数和"
    first_reaction: "先排序。"
    key_transformation: "排序。"
    solution_skeleton:
      - "排序"
    common_traps: []
    general_template: "先找极端结构。"
    training_use: "训练。"
    human_notes: ""
  translation:
    model: manual:codex-reviewed
    review_status: machine_draft
""",
    )
    write_yaml(source_root / "p12403_2.yaml", "id: imported.amm_analysis_training_full_source.p12403_2")

    audit_path = tmp_path / "audit.json"
    manifest_path = tmp_path / "manifest.json"
    audit_path.write_text(
        json.dumps(
            {
                "source_count": 1,
                "translated_count": 1,
                "missing_translation_count": 0,
                "failure_count": 0,
                "format_issues": [],
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps({"records": []}), encoding="utf-8")

    summary = build_site(output_root, zh_root, source_root, audit_path, manifest_path, copy_yaml=True)

    assert summary["records"] == 1
    assert (output_root / "docs/index.html").exists()
    assert (output_root / "docs/assets/site.css").exists()
    assert (output_root / "docs/assets/site.js").exists()
    assert (output_root / "docs/data/questions.json").exists()
    assert (output_root / "docs/data/stats.json").exists()
    assert (output_root / "source/manifest.json").exists()
    assert (output_root / "source/audit.json").exists()
    assert (output_root / "source/bank-yaml/p12403_2.yaml").exists()

    questions = json.loads((output_root / "docs/data/questions.json").read_text(encoding="utf-8"))
    assert questions[0]["id"] == "imported.amm_analysis_training_full_zh.p12403_2"


def test_write_site_assets_contains_viewer_hooks(tmp_path):
    from build_static_amm_site import write_site_assets

    write_site_assets(tmp_path)

    html = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    css = (tmp_path / "docs/assets/site.css").read_text(encoding="utf-8")
    js = (tmp_path / "docs/assets/site.js").read_text(encoding="utf-8")

    assert "data/questions.json" in html
    assert "MathJax" in html
    assert (tmp_path / "docs/.nojekyll").exists()
    assert 'id="search-input"' in html
    assert 'id="domain-filters"' in html
    assert 'id="question-list"' in html
    assert 'id="question-detail"' in html
    assert ".layout" in css
    assert "white-space: pre-wrap" in css
    assert "function applyFilters" in js
    assert "function renderQuestion" in js
    assert "function parseHash" in js
    assert "tikzpicture" in js
    assert 'replace(/\\n/g, "<br>")' not in js


def test_real_bank_export_has_expected_counts_when_data_exists(tmp_path):
    from build_static_amm_site import (
        DEFAULT_AUDIT_PATH,
        DEFAULT_MANIFEST_PATH,
        DEFAULT_SOURCE_ROOT,
        DEFAULT_ZH_ROOT,
        build_site,
    )

    if not DEFAULT_ZH_ROOT.exists() or not DEFAULT_AUDIT_PATH.exists():
        return

    output_root = tmp_path / "export"
    summary = build_site(
        output_root,
        DEFAULT_ZH_ROOT,
        DEFAULT_SOURCE_ROOT,
        DEFAULT_AUDIT_PATH,
        DEFAULT_MANIFEST_PATH,
        copy_yaml=False,
    )

    assert summary["records"] == 981
    questions = json.loads((output_root / "docs/data/questions.json").read_text(encoding="utf-8"))
    assert len(questions) == 981
    assert any(question["domain"] == "inequality" and question["priority"] == "high" for question in questions)
    assert any(question["domain"] == "analysis" for question in questions)
    assert any(question["review_flag"] == "clean_required" for question in questions)


def test_summarize_for_cli_omits_large_tag_maps():
    from build_static_amm_site import summarize_for_cli

    summary = {
        "records": 2,
        "output_root": "dist/amm-analysis-training",
        "stats": {
            "total": 2,
            "domains": {"analysis": 1, "inequality": 1},
            "priorities": {"high": 1, "medium": 1},
            "review_flags": {"auto_ok": 1, "needs_review": 1},
            "tags": {"very long tag": 1},
            "methods": {"very long method": 1},
        },
    }

    cli_summary = summarize_for_cli(summary)

    assert cli_summary == {
        "records": 2,
        "output_root": "dist/amm-analysis-training",
        "domains": {"analysis": 1, "inequality": 1},
        "priorities": {"high": 1, "medium": 1},
        "review_flags": {"auto_ok": 1, "needs_review": 1},
    }
