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
