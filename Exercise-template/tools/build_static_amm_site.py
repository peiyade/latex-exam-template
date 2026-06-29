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
