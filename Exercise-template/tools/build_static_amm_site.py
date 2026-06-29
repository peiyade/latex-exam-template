#!/usr/bin/env python3
"""Build a static GitHub Pages site for the AMM training bank."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List

from question_loader import load_question_file


DEFAULT_ZH_ROOT = Path("bank/_curated/amm_analysis_training_full_zh")
DEFAULT_SOURCE_ROOT = Path("bank/_curated/amm_analysis_training_full_source")
DEFAULT_AUDIT_PATH = Path("analysis/amm_analysis_training_full_audit.json")
DEFAULT_MANIFEST_PATH = Path("analysis/amm_analysis_training_full_manifest.json")
DEFAULT_OUTPUT_ROOT = Path("dist/amm-analysis-training")


REQUIRED_CURATION_FIELDS = ("main_domain", "priority_for_course", "review_flag")


def normalize_question(record: Dict[str, Any]) -> Dict[str, Any]:
    metadata = record.get("metadata", {})
    curation = metadata.get("curation", {})
    training_card = metadata.get("training_card", {})
    source = record.get("source", {})
    stem = str(record.get("stem_latex", "")).strip()
    solution = str(record.get("solution_latex", "")).strip()
    title = str(record.get("comment") or metadata.get("section_title") or record["id"])
    tags = list(curation.get("structure_tags", []) or [])
    methods = list(curation.get("candidate_methods", []) or [])
    search_parts = [
        record["id"],
        str(source.get("translation_of", "")),
        str(metadata.get("problem_number", "")),
        title,
        str(curation.get("basic_judgment", "")),
        " ".join(tags),
        " ".join(methods),
        str(training_card.get("first_reaction", "")),
        str(training_card.get("key_transformation", "")),
        stem,
    ]
    text_blob = "\n".join([stem, solution])
    return {
        "id": record["id"],
        "source_id": source.get("translation_of", ""),
        "legacy_id": source.get("legacy_id", ""),
        "problem_number": metadata.get("problem_number"),
        "title": title,
        "domain": curation.get("main_domain", ""),
        "priority": curation.get("priority_for_course", ""),
        "review_flag": curation.get("review_flag", ""),
        "status": record.get("status", ""),
        "type": record.get("type", ""),
        "tags": tags,
        "methods": methods,
        "recognition_cues": list(training_card.get("recognition_cues", []) or []),
        "first_reaction": training_card.get("first_reaction", ""),
        "key_transformation": training_card.get("key_transformation", ""),
        "solution_skeleton": list(training_card.get("solution_skeleton", []) or []),
        "common_traps": list(training_card.get("common_traps", []) or []),
        "general_template": training_card.get("general_template", ""),
        "training_use": training_card.get("training_use", ""),
        "human_notes": training_card.get("human_notes", ""),
        "basic_judgment": curation.get("basic_judgment", ""),
        "data_quality_flags": list(curation.get("data_quality_flags", []) or []),
        "stem_latex": stem,
        "solution_latex": solution,
        "source_preview_url": source.get("preview_url", ""),
        "translation_model": metadata.get("translation", {}).get("model", ""),
        "translation_review_status": metadata.get("translation", {}).get("review_status", ""),
        "has_tikz": "tikzpicture" in text_blob,
        "search_text": " ".join(part for part in search_parts if part).lower(),
    }


def compute_stats(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total": len(questions),
        "domains": count_values(question["domain"] for question in questions),
        "priorities": count_values(question["priority"] for question in questions),
        "review_flags": count_values(question["review_flag"] for question in questions),
        "tags": count_values(tag for question in questions for tag in question["tags"]),
        "methods": count_values(method for question in questions for method in question["methods"]),
    }


def count_values(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def load_questions(zh_root: Path) -> List[Dict[str, Any]]:
    records = [load_question_file(path) for path in sorted(zh_root.glob("*.yaml"))]
    questions = [normalize_question(record) for record in records]
    questions.sort(key=lambda item: (str(item.get("problem_number", "")), item["id"]))
    validate_questions(questions)
    return questions


def validate_questions(questions: List[Dict[str, Any]]) -> None:
    if not questions:
        raise ValueError("no questions loaded")
    for question in questions:
        for field in ("id", "title", "domain", "priority", "review_flag", "stem_latex"):
            if not question.get(field):
                raise ValueError(f"{question.get('id', '<unknown>')}: missing required field {field}")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_audit(audit: Dict[str, Any]) -> None:
    if audit.get("source_count") != audit.get("translated_count"):
        raise ValueError(
            "audit source_count and translated_count differ: "
            f"{audit.get('source_count')} != {audit.get('translated_count')}"
        )
    if audit.get("missing_translation_count") != 0:
        raise ValueError(f"audit missing_translation_count is {audit.get('missing_translation_count')}")
    if audit.get("failure_count") != 0:
        raise ValueError(f"audit failure_count is {audit.get('failure_count')}")
    if audit.get("format_issues"):
        raise ValueError(f"audit format_issues is not empty: {audit.get('format_issues')}")


def build_site(
    output_root: Path,
    zh_root: Path,
    source_root: Path,
    audit_path: Path,
    manifest_path: Path,
    copy_yaml: bool = True,
) -> Dict[str, Any]:
    audit = read_json(audit_path)
    validate_audit(audit)
    questions = load_questions(zh_root)
    stats = compute_stats(questions)

    if output_root.exists():
        shutil.rmtree(output_root)
    (output_root / "docs/assets").mkdir(parents=True, exist_ok=True)
    (output_root / "docs/data").mkdir(parents=True, exist_ok=True)
    (output_root / "source").mkdir(parents=True, exist_ok=True)

    write_json(output_root / "docs/data/questions.json", questions)
    write_json(output_root / "docs/data/stats.json", stats)
    shutil.copy2(audit_path, output_root / "source/audit.json")
    shutil.copy2(manifest_path, output_root / "source/manifest.json")
    if copy_yaml:
        copy_bank_yaml(zh_root, output_root / "source/bank-yaml")

    write_site_assets(output_root)
    write_readme(output_root, stats)
    write_builder_copy(output_root)
    return {"records": len(questions), "stats": stats, "output_root": str(output_root)}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_bank_yaml(zh_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(zh_root.glob("*.yaml")):
        shutil.copy2(source_path, target_root / source_path.name)


def write_builder_copy(output_root: Path) -> None:
    tools_dir = output_root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), tools_dir / "build_static_site.py")


def write_site_assets(output_root: Path) -> None:
    (output_root / "docs/index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>AMM Analysis Training</title>"
        "<main id='app'>AMM Analysis Training</main>"
        "<script src='assets/site.js'></script>\n",
        encoding="utf-8",
    )
    (output_root / "docs/assets/site.css").write_text("body { font-family: serif; }\n", encoding="utf-8")
    (output_root / "docs/assets/site.js").write_text("console.log('AMM site');\n", encoding="utf-8")


def write_readme(output_root: Path, stats: Dict[str, Any]) -> None:
    (output_root / "README.md").write_text(
        "# AMM Analysis Training\n\n"
        "Static GitHub Pages site for the AMM analysis / inequality / extremum training bank.\n\n"
        f"Records: {stats['total']}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AMM static GitHub Pages site.")
    parser.add_argument("--zh-root", type=Path, default=DEFAULT_ZH_ROOT)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--no-copy-yaml", action="store_true")
    args = parser.parse_args()

    summary = build_site(
        args.output_root,
        args.zh_root,
        args.source_root,
        args.audit,
        args.manifest,
        copy_yaml=not args.no_copy_yaml,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
