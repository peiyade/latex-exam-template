# AMM Static Pages Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a distributable GitHub Pages static site for the 981-problem AMM analysis / inequality / extremum Chinese training bank.

**Architecture:** Add a Python static-site builder that validates the completed YAML bank, normalizes records into JSON, and writes a self-contained `docs/` site into a separate export directory. The viewer is a single static HTML app that loads `data/questions.json`, renders MathJax formulas, and provides search, filters, tags, and shareable hash URLs without a backend.

**Tech Stack:** Python 3, existing `tools/question_loader.py`, existing AMM audit script, vanilla HTML/CSS/JavaScript, MathJax CDN, GitHub CLI `gh`.

## Global Constraints

- Export repository name is `amm-analysis-training`.
- GitHub Pages publishes from `main` branch, `/docs` directory.
- The YAML bank remains the source of truth.
- Primary display source is `bank/_curated/amm_analysis_training_full_zh`.
- Curated source bank is `bank/_curated/amm_analysis_training_full_source`.
- Builder must fail if source count and translated count differ.
- Builder must fail if audit reports unresolved failures or format issues.
- First version is a static reference site, not an editing system and not a backend audit system.
- Use MathJax for math rendering.
- TikZ is not a hard dependency in version 1; show TikZ source as fallback text.
- Generated site must support search, `domain`, `priority`, `review_flag`, tag/method filtering, and shareable URL hash state.

---

## File Structure

Create or modify these files in the current working repository:

```text
tools/build_static_amm_site.py
tests/test_build_static_amm_site.py
```

The builder writes an export repository directory, defaulting to:

```text
dist/amm-analysis-training/
  docs/
    index.html
    assets/
      site.css
      site.js
    data/
      questions.json
      stats.json
  source/
    bank-yaml/
    manifest.json
    audit.json
  tools/
    build_static_site.py
  README.md
```

`tools/build_static_amm_site.py` responsibilities:

- load YAML records from the completed Chinese bank;
- run or read the AMM audit;
- normalize metadata into compact JSON;
- write static app files;
- optionally copy YAML source records into `source/bank-yaml`;
- write a README for the export repository;
- print a deterministic summary.

`tests/test_build_static_amm_site.py` responsibilities:

- verify record normalization;
- verify stats generation;
- verify audit gating;
- verify `build_site(...)` writes the expected static files;
- verify generated JS/HTML contains required UI hooks.

---

### Task 1: Export Record Normalization And Stats

**Files:**
- Create: `tools/build_static_amm_site.py`
- Create: `tests/test_build_static_amm_site.py`

**Interfaces:**
- Consumes: loaded question record dictionaries from `tools/question_loader.py`
- Produces: `normalize_question(record: dict[str, object]) -> dict[str, object]`
- Produces: `compute_stats(questions: list[dict[str, object]]) -> dict[str, object]`

- [ ] **Step 1: Write failing normalization and stats tests**

Create `tests/test_build_static_amm_site.py`:

```python
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
    q2 = {**q1, "id": "q2", "domain": "analysis", "priority": "medium", "review_flag": "auto_ok", "tags": ["极限"]}

    stats = compute_stats([q1, q2])

    assert stats["total"] == 2
    assert stats["domains"] == {"analysis": 1, "inequality": 1}
    assert stats["priorities"] == {"high": 1, "medium": 1}
    assert stats["review_flags"] == {"auto_ok": 1, "needs_review": 1}
    assert stats["tags"]["五变量不等式"] == 1
    assert stats["tags"]["极限"] == 1
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'build_static_amm_site'`.

- [ ] **Step 3: Implement normalization and stats**

Create `tools/build_static_amm_site.py`:

```python
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
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/build_static_amm_site.py tests/test_build_static_amm_site.py
git commit -m "feat: normalize AMM static site records"
```

Expected: commit succeeds.

---

### Task 2: Site Builder Validation And File Output

**Files:**
- Modify: `tools/build_static_amm_site.py`
- Modify: `tests/test_build_static_amm_site.py`

**Interfaces:**
- Consumes: `normalize_question(record) -> dict[str, object]`
- Produces: `load_questions(zh_root: Path) -> list[dict[str, object]]`
- Produces: `validate_audit(audit: dict[str, object]) -> None`
- Produces: `build_site(output_root: Path, zh_root: Path, source_root: Path, audit_path: Path, manifest_path: Path, copy_yaml: bool = True) -> dict[str, object]`

- [ ] **Step 1: Add failing tests for audit gating and output files**

Append to `tests/test_build_static_amm_site.py`:

```python
import json


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

    record = sample_record()
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py -q
```

Expected: fail with missing `validate_audit` and `build_site`.

- [ ] **Step 3: Implement audit validation, question loading, and site file output**

Append these functions to `tools/build_static_amm_site.py`:

```python
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
            f"audit source_count and translated_count differ: "
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
```

Add temporary asset writers; Task 3 will replace them with the full viewer:

```python
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
```

- [ ] **Step 4: Add CLI entry point**

Append to `tools/build_static_amm_site.py`:

```python
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
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py -q
```

Expected: all tests in this file pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add tools/build_static_amm_site.py tests/test_build_static_amm_site.py
git commit -m "feat: build AMM static site export"
```

Expected: commit succeeds.

---

### Task 3: Static Viewer HTML, CSS, And JavaScript

**Files:**
- Modify: `tools/build_static_amm_site.py`
- Modify: `tests/test_build_static_amm_site.py`

**Interfaces:**
- Consumes: `docs/data/questions.json`
- Produces: `docs/index.html`
- Produces: `docs/assets/site.css`
- Produces: `docs/assets/site.js`
- Browser API: hash state accepts `#q=<question-id>`, `#domain=<domain>`, `#priority=<priority>`, `#review=<review_flag>`, `#tag=<tag>`, `#method=<method>`, `#s=<search>`

- [ ] **Step 1: Add failing tests for viewer hooks**

Append to `tests/test_build_static_amm_site.py`:

```python
def test_write_site_assets_contains_viewer_hooks(tmp_path):
    from build_static_amm_site import write_site_assets

    write_site_assets(tmp_path)

    html = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    css = (tmp_path / "docs/assets/site.css").read_text(encoding="utf-8")
    js = (tmp_path / "docs/assets/site.js").read_text(encoding="utf-8")

    assert "data/questions.json" in html
    assert "MathJax" in html
    assert 'id="search-input"' in html
    assert 'id="domain-filters"' in html
    assert 'id="question-list"' in html
    assert 'id="question-detail"' in html
    assert ".layout" in css
    assert "function applyFilters" in js
    assert "function renderQuestion" in js
    assert "function parseHash" in js
    assert "tikzpicture" in js
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py::test_write_site_assets_contains_viewer_hooks -q
```

Expected: fails because the temporary minimal assets do not contain the required hooks.

- [ ] **Step 3: Replace `write_site_assets` with full asset writer**

Replace the temporary `write_site_assets` in `tools/build_static_amm_site.py` with:

```python
def write_site_assets(output_root: Path) -> None:
    docs_root = output_root / "docs"
    assets_root = docs_root / "assets"
    docs_root.mkdir(parents=True, exist_ok=True)
    assets_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (assets_root / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (assets_root / "site.js").write_text(SITE_JS, encoding="utf-8")
```

Add `INDEX_HTML`, `SITE_CSS`, and `SITE_JS` constants near the bottom of the file.

Use this `INDEX_HTML`:

```python
INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AMM Analysis Training</title>
  <link rel="stylesheet" href="assets/site.css">
  <script>
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\(', '\\)']],
        displayMath: [['$$', '$$'], ['\\[', '\\]']]
      },
      startup: { typeset: false }
    };
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
  <script defer src="assets/site.js"></script>
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">AMM Analysis / Inequality / Extremum</p>
      <h1>模式识别训练题库</h1>
    </div>
    <div class="stats" id="stats"></div>
  </header>
  <main class="layout">
    <aside class="sidebar">
      <label class="search-label" for="search-input">搜索</label>
      <input id="search-input" type="search" aria-label="题号、tag、方法、关键词">
      <section>
        <h2>领域</h2>
        <div class="chip-row" id="domain-filters"></div>
      </section>
      <section>
        <h2>优先级</h2>
        <div class="chip-row" id="priority-filters"></div>
      </section>
      <section>
        <h2>状态</h2>
        <div class="chip-row" id="review-filters"></div>
      </section>
      <section>
        <h2>结构 Tags</h2>
        <select id="tag-filter"><option value="">全部</option></select>
      </section>
      <section>
        <h2>方法 Tags</h2>
        <select id="method-filter"><option value="">全部</option></select>
      </section>
    </aside>
    <section class="results">
      <div class="result-head">
        <strong id="result-count">0</strong>
        <button id="clear-filters" type="button">清除筛选</button>
      </div>
      <div id="question-list" class="question-list"></div>
    </section>
    <article id="question-detail" class="detail" aria-live="polite"></article>
  </main>
  <script type="application/json" id="site-data-src">data/questions.json</script>
</body>
</html>
"""
```

Use this `SITE_CSS`:

```python
SITE_CSS = r"""* { box-sizing: border-box; }
body {
  margin: 0;
  color: #24211d;
  background: #f5efe4;
  font-family: Georgia, "Noto Serif SC", "Source Han Serif SC", serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 32px 18px;
  border-bottom: 1px solid #d8cbb6;
  background: #fffaf0;
}
.eyebrow { margin: 0 0 6px; color: #0a665a; font-weight: 700; }
h1 { margin: 0; font-size: 32px; line-height: 1.05; }
.stats { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; align-content: start; }
.stat-pill, .badge, .chip {
  border: 1px solid #cdbf9e;
  background: #fffaf0;
  padding: 6px 9px;
  font-weight: 700;
}
.layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(300px, 440px) minmax(520px, 1fr);
  gap: 16px;
  padding: 16px;
  min-height: calc(100vh - 105px);
}
.sidebar, .results, .detail {
  background: #fffaf0;
  border: 1px solid #d6c8b1;
  min-width: 0;
}
.sidebar { padding: 16px; position: sticky; top: 16px; height: calc(100vh - 137px); overflow: auto; }
.sidebar h2 { font-size: 14px; margin: 18px 0 8px; color: #6e675b; }
.search-label { display: block; font-weight: 700; margin-bottom: 8px; }
input, select, button {
  width: 100%;
  border: 1px solid #cdbf9e;
  background: #fffaf0;
  color: #24211d;
  padding: 9px 10px;
  font: 700 14px/1.2 system-ui, sans-serif;
}
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { width: auto; cursor: pointer; }
.chip.is-active { background: #0a665a; border-color: #0a665a; color: #fffaf0; }
.results { overflow: auto; }
.result-head {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid #d6c8b1;
  background: #fffaf0;
}
.result-head button { width: auto; }
.question-card {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  border-bottom: 1px solid #e1d7c6;
  background: transparent;
  padding: 14px 12px;
  cursor: pointer;
}
.question-card.is-selected { background: #eee6d8; box-shadow: inset 3px 0 0 #0a665a; }
.question-title { font-size: 18px; font-weight: 800; line-height: 1.2; margin-bottom: 7px; }
.question-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 7px; }
.question-summary { color: #5f584e; font-size: 14px; line-height: 1.45; }
.detail { padding: 24px 28px; overflow: auto; }
.detail h2 { font-size: 34px; line-height: 1.08; margin: 0 0 12px; }
.detail-section { border-top: 1px solid #d6c8b1; padding-top: 18px; margin-top: 20px; }
.detail-section h3 { margin: 0 0 10px; color: #0a665a; font-size: 18px; }
.latex-block { font-size: 19px; line-height: 1.85; overflow-x: auto; }
.card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.info-card { border: 1px solid #d6c8b1; padding: 12px; background: #fffdf7; }
.info-card strong { display: block; margin-bottom: 6px; color: #6e675b; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.source-block { color: #625a50; font-size: 14px; line-height: 1.6; }
pre.tikz-source { white-space: pre-wrap; overflow-x: auto; padding: 12px; background: #f0eadf; border: 1px solid #d6c8b1; }
@media (max-width: 1100px) {
  .layout { grid-template-columns: 280px 1fr; }
  .detail { grid-column: 1 / -1; }
  .sidebar { height: auto; position: static; }
}
@media (max-width: 760px) {
  .topbar { display: block; padding: 18px; }
  .layout { display: block; padding: 10px; }
  .sidebar, .results, .detail { margin-bottom: 12px; }
  .card-grid { grid-template-columns: 1fr; }
  .detail h2 { font-size: 26px; }
}
"""
```

Use this `SITE_JS`:

```python
SITE_JS = r"""const state = {
  questions: [],
  filtered: [],
  selectedId: "",
  search: "",
  domain: "",
  priority: "",
  review: "",
  tag: "",
  method: ""
};

document.addEventListener("DOMContentLoaded", async () => {
  const response = await fetch("data/questions.json");
  state.questions = await response.json();
  state.questions.sort((a, b) => String(a.problem_number || "").localeCompare(String(b.problem_number || "")) || a.id.localeCompare(b.id));
  renderStats();
  hydrateControls();
  Object.assign(state, parseHash());
  syncControlsFromState();
  applyFilters();
});

function parseHash() {
  const hash = window.location.hash.replace(/^#/, "");
  const params = new URLSearchParams(hash);
  return {
    selectedId: params.get("q") || "",
    search: params.get("s") || "",
    domain: params.get("domain") || "",
    priority: params.get("priority") || "",
    review: params.get("review") || "",
    tag: params.get("tag") || "",
    method: params.get("method") || ""
  };
}

function writeHash() {
  const params = new URLSearchParams();
  if (state.selectedId) params.set("q", state.selectedId);
  if (state.search) params.set("s", state.search);
  if (state.domain) params.set("domain", state.domain);
  if (state.priority) params.set("priority", state.priority);
  if (state.review) params.set("review", state.review);
  if (state.tag) params.set("tag", state.tag);
  if (state.method) params.set("method", state.method);
  window.history.replaceState(null, "", "#" + params.toString());
}

function renderStats() {
  const stats = document.getElementById("stats");
  const total = state.questions.length;
  const high = state.questions.filter(q => q.priority === "high").length;
  const cleanRequired = state.questions.filter(q => q.review_flag === "clean_required").length;
  stats.innerHTML = [
    pill(`${total} 题`),
    pill(`High ${high}`),
    pill(`Clean ${cleanRequired}`)
  ].join("");
}

function hydrateControls() {
  makeChips("domain-filters", ["analysis", "inequality", "extremum"], "domain");
  makeChips("priority-filters", ["high", "medium", "low"], "priority");
  makeChips("review-filters", ["auto_ok", "needs_review", "clean_required"], "review");
  populateSelect("tag-filter", uniqueValues(q => q.tags));
  populateSelect("method-filter", uniqueValues(q => q.methods));
  document.getElementById("search-input").addEventListener("input", event => {
    state.search = event.target.value.trim().toLowerCase();
    applyFilters();
  });
  document.getElementById("tag-filter").addEventListener("change", event => {
    state.tag = event.target.value;
    applyFilters();
  });
  document.getElementById("method-filter").addEventListener("change", event => {
    state.method = event.target.value;
    applyFilters();
  });
  document.getElementById("clear-filters").addEventListener("click", () => {
    state.search = "";
    state.domain = "";
    state.priority = "";
    state.review = "";
    state.tag = "";
    state.method = "";
    state.selectedId = "";
    syncControlsFromState();
    applyFilters();
  });
}

function makeChips(containerId, values, field) {
  const container = document.getElementById(containerId);
  container.innerHTML = values.map(value => `<button class="chip" type="button" data-field="${field}" data-value="${escapeHtml(value)}">${escapeHtml(value)}</button>`).join("");
  container.querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      state[field] = state[field] === button.dataset.value ? "" : button.dataset.value;
      syncControlsFromState();
      applyFilters();
    });
  });
}

function populateSelect(id, values) {
  const select = document.getElementById(id);
  select.innerHTML = '<option value="">全部</option>' + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

function uniqueValues(project) {
  return [...new Set(state.questions.flatMap(project).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
}

function syncControlsFromState() {
  document.getElementById("search-input").value = state.search;
  document.getElementById("tag-filter").value = state.tag;
  document.getElementById("method-filter").value = state.method;
  document.querySelectorAll(".chip").forEach(button => {
    button.classList.toggle("is-active", state[button.dataset.field] === button.dataset.value);
  });
}

function applyFilters() {
  state.filtered = state.questions.filter(question => {
    if (state.search && !question.search_text.includes(state.search)) return false;
    if (state.domain && question.domain !== state.domain) return false;
    if (state.priority && question.priority !== state.priority) return false;
    if (state.review && question.review_flag !== state.review) return false;
    if (state.tag && !question.tags.includes(state.tag)) return false;
    if (state.method && !question.methods.includes(state.method)) return false;
    return true;
  });
  if (!state.selectedId || !state.filtered.some(question => question.id === state.selectedId)) {
    state.selectedId = state.filtered[0]?.id || "";
  }
  renderQuestionList();
  renderQuestion(state.questions.find(question => question.id === state.selectedId));
  writeHash();
}

function renderQuestionList() {
  document.getElementById("result-count").textContent = `${state.filtered.length} / ${state.questions.length}`;
  const list = document.getElementById("question-list");
  list.innerHTML = state.filtered.map(question => `
    <button class="question-card ${question.id === state.selectedId ? "is-selected" : ""}" type="button" data-id="${escapeHtml(question.id)}">
      <div class="question-title">${escapeHtml(question.problem_number || "")} · ${escapeHtml(question.title)}</div>
      <div class="question-meta">${pill(question.domain)}${pill(question.priority)}${pill(question.review_flag)}</div>
      <div class="question-summary">${escapeHtml(question.first_reaction || question.basic_judgment || "")}</div>
    </button>
  `).join("");
  list.querySelectorAll(".question-card").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedId = button.dataset.id;
      renderQuestionList();
      renderQuestion(state.questions.find(question => question.id === state.selectedId));
      writeHash();
    });
  });
}

function renderQuestion(question) {
  const detail = document.getElementById("question-detail");
  if (!question) {
    detail.innerHTML = "<p>没有匹配的题目。</p>";
    return;
  }
  detail.innerHTML = `
    <h2>${escapeHtml(question.problem_number || "")} · ${escapeHtml(question.title)}</h2>
    <div class="question-meta">${pill(question.domain)}${pill(question.priority)}${pill(question.review_flag)}${question.has_tikz ? pill("tikz source") : ""}</div>
    <section class="detail-section">
      <h3>题干</h3>
      <div class="latex-block">${renderLatexText(question.stem_latex)}</div>
    </section>
    <section class="detail-section">
      <h3>模式识别</h3>
      <div class="card-grid">
        ${infoCard("第一反应", question.first_reaction || question.basic_judgment)}
        ${infoCard("关键变换", question.key_transformation)}
        ${infoCard("训练用途", question.training_use)}
        ${infoCard("通用模板", question.general_template)}
      </div>
      <div class="tag-list">${[...question.tags, ...question.methods].map(pill).join("")}</div>
    </section>
    <section class="detail-section">
      <h3>解答</h3>
      <div class="latex-block">${renderLatexText(question.solution_latex || "暂无解答。")}</div>
    </section>
    <section class="detail-section">
      <h3>风险与来源</h3>
      ${listBlock("常见陷阱", question.common_traps)}
      ${listBlock("数据质量", question.data_quality_flags)}
      <div class="source-block">
        <div>id: ${escapeHtml(question.id)}</div>
        <div>source: ${escapeHtml(question.source_id)}</div>
        <div>legacy: ${escapeHtml(question.legacy_id || "")}</div>
        <div>model: ${escapeHtml(question.translation_model || "")}</div>
      </div>
    </section>
  `;
  typesetMath();
}

function infoCard(title, value) {
  return `<div class="info-card"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(value || "—")}</span></div>`;
}

function listBlock(title, values) {
  if (!values || !values.length) return "";
  return `<div class="info-card"><strong>${escapeHtml(title)}</strong><ul>${values.map(value => `<li>${escapeHtml(value)}</li>`).join("")}</ul></div>`;
}

function renderLatexText(text) {
  if (!text) return "";
  const escaped = escapeHtml(text).replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
  const html = `<p>${escaped}</p>`;
  if (text.includes("tikzpicture")) {
    return html + `<pre class="tikz-source">${escapeHtml(text)}</pre>`;
  }
  return html;
}

function typesetMath() {
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise([document.getElementById("question-detail")]).catch(console.error);
  }
}

function pill(text) {
  return `<span class="badge">${escapeHtml(String(text || ""))}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
"""
```

- [ ] **Step 4: Run viewer hook tests**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py::test_write_site_assets_contains_viewer_hooks -q
```

Expected: pass.

- [ ] **Step 5: Run all static-site builder tests**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add tools/build_static_amm_site.py tests/test_build_static_amm_site.py
git commit -m "feat: add AMM static site viewer"
```

Expected: commit succeeds.

---

### Task 4: Build Full Export And Add Local Verification

**Files:**
- Modify: `tests/test_build_static_amm_site.py`
- Output: `dist/amm-analysis-training/`

**Interfaces:**
- Command: `python3 tools/build_static_amm_site.py --output-root dist/amm-analysis-training`
- Consumes: completed 981-record bank and audit JSON.
- Produces: complete export directory ready for GitHub Pages.

- [ ] **Step 1: Add failing integration test for full-bank export shape**

Append to `tests/test_build_static_amm_site.py`:

```python
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
```

- [ ] **Step 2: Run integration test**

Run:

```bash
python3 -m pytest tests/test_build_static_amm_site.py::test_real_bank_export_has_expected_counts_when_data_exists -q
```

Expected: pass if the full bank is present; otherwise skip-like early return.

- [ ] **Step 3: Run audit before building**

Run:

```bash
python3 tools/audit_amm_training_bank.py > /tmp/amm_static_site_audit.txt
cat /tmp/amm_static_site_audit.txt
```

Expected:

```text
"source_count": 981
"translated_count": 981
"missing_translation_count": 0
"failure_count": 0
"format_issues": []
```

- [ ] **Step 4: Build full export**

Run:

```bash
python3 tools/build_static_amm_site.py --output-root dist/amm-analysis-training
```

Expected: JSON summary includes `"records": 981` and output root `dist/amm-analysis-training`.

- [ ] **Step 5: Serve generated docs locally**

Run:

```bash
python3 -m http.server 8010 --directory dist/amm-analysis-training/docs
```

Expected: server listens on `http://0.0.0.0:8010/`.

If running in a terminal session, keep it active until the browser checks finish.

- [ ] **Step 6: Verify generated site over HTTP**

Run in another terminal:

```bash
python3 - <<'PY'
from urllib.request import urlopen
for url in [
    "http://127.0.0.1:8010/",
    "http://127.0.0.1:8010/data/questions.json",
    "http://127.0.0.1:8010/data/stats.json",
]:
    with urlopen(url, timeout=20) as response:
        body = response.read()
    print(url, response.status, len(body))
PY
```

Expected: all three URLs return status `200`; `questions.json` is larger than 1 MB.

- [ ] **Step 7: Verify JSON content**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
questions = json.loads(Path("dist/amm-analysis-training/docs/data/questions.json").read_text(encoding="utf-8"))
stats = json.loads(Path("dist/amm-analysis-training/docs/data/stats.json").read_text(encoding="utf-8"))
print(len(questions))
print(stats["total"])
print(stats["domains"])
print(stats["priorities"])
print(stats["review_flags"])
assert len(questions) == 981
assert stats["total"] == 981
assert "analysis" in stats["domains"]
assert "inequality" in stats["domains"]
assert "extremum" in stats["domains"]
assert "high" in stats["priorities"]
assert "clean_required" in stats["review_flags"]
PY
```

Expected: assertions pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add tools/build_static_amm_site.py tests/test_build_static_amm_site.py dist/amm-analysis-training
git commit -m "feat: export AMM static training site"
```

Expected: commit succeeds.

---

### Task 5: GitHub Pages Repository Setup

**Files:**
- Output repository: `dist/amm-analysis-training`
- Optional helper script: `dist/amm-analysis-training/publish.sh`

**Interfaces:**
- Consumes: generated `dist/amm-analysis-training`
- Produces: GitHub repository `amm-analysis-training`
- Produces: GitHub Pages URL `https://<github-user>.github.io/amm-analysis-training/`

- [ ] **Step 1: Confirm GitHub CLI authentication**

Run:

```bash
gh auth status
```

Expected: authenticated to GitHub.com with an account that can create repositories.

- [ ] **Step 2: Initialize export repository if needed**

Run:

```bash
cd dist/amm-analysis-training
git init
git add README.md docs source tools
git commit -m "Initial AMM analysis training site"
```

Expected: commit succeeds.

- [ ] **Step 3: Create or connect GitHub repository**

If the repository does not exist, run:

```bash
cd dist/amm-analysis-training
gh repo create amm-analysis-training --public --source=. --remote=origin --push
```

Expected: repository is created and pushed.

If the repository already exists, run:

```bash
cd dist/amm-analysis-training
git remote add origin git@github.com:$(gh api user --jq .login)/amm-analysis-training.git 2>/dev/null || true
git branch -M main
git push -u origin main
```

Expected: branch `main` is pushed to `origin`.

- [ ] **Step 4: Enable GitHub Pages from `/docs`**

Try `POST` first:

```bash
cd dist/amm-analysis-training
OWNER=$(gh api user --jq .login)
gh api "repos/$OWNER/amm-analysis-training/pages" \
  -X POST \
  -f source.branch=main \
  -f source.path=/docs
```

Expected: succeeds if Pages was not already enabled.

If GitHub returns an already-exists error, run:

```bash
cd dist/amm-analysis-training
OWNER=$(gh api user --jq .login)
gh api "repos/$OWNER/amm-analysis-training/pages" \
  -X PATCH \
  -f source.branch=main \
  -f source.path=/docs
```

Expected: Pages source is updated to `main` `/docs`.

- [ ] **Step 5: Verify Pages URL**

Run:

```bash
cd dist/amm-analysis-training
OWNER=$(gh api user --jq .login)
echo "https://$OWNER.github.io/amm-analysis-training/"
python3 - <<'PY'
from urllib.request import urlopen
import subprocess
owner = subprocess.check_output(["gh", "api", "user", "--jq", ".login"], text=True).strip()
url = f"https://{owner}.github.io/amm-analysis-training/"
with urlopen(url, timeout=60) as response:
    body = response.read().decode("utf-8", errors="replace")
print(response.status, len(body), "AMM Analysis Training" in body)
PY
```

Expected: status `200` and output contains `True`. If GitHub Pages is still building, wait 60 seconds and rerun.

- [ ] **Step 6: Commit publish helper in export repository**

Create `dist/amm-analysis-training/publish.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

git add README.md docs source tools
git commit -m "Update AMM analysis training site" || true
git push

OWNER=$(gh api user --jq .login)
gh api "repos/$OWNER/amm-analysis-training/pages" \
  -X PATCH \
  -f source.branch=main \
  -f source.path=/docs >/dev/null

echo "https://$OWNER.github.io/amm-analysis-training/"
```

Run:

```bash
cd dist/amm-analysis-training
chmod +x publish.sh
git add publish.sh
git commit -m "chore: add publish helper"
git push
```

Expected: helper script is committed and pushed.

---

## Final Verification

Run these commands from `/Users/vitamin-k/Documents/latex-exam-template/Exercise-template`:

```bash
python3 -m pytest tests/test_build_static_amm_site.py tests/test_audit_amm_training_bank.py -q
python3 -m py_compile tools/build_static_amm_site.py
python3 tools/audit_amm_training_bank.py > /tmp/amm_static_final_audit.txt
python3 tools/build_static_amm_site.py --output-root dist/amm-analysis-training
python3 - <<'PY'
import json
from pathlib import Path
questions = json.loads(Path("dist/amm-analysis-training/docs/data/questions.json").read_text(encoding="utf-8"))
assert len(questions) == 981
assert any(q["domain"] == "inequality" and q["priority"] == "high" for q in questions)
assert any(q["domain"] == "analysis" for q in questions)
assert any(q["domain"] == "extremum" for q in questions)
assert any(q["review_flag"] == "clean_required" for q in questions)
print("static export verified", len(questions))
PY
```

Expected:

- all pytest tests pass;
- `py_compile` exits 0;
- final audit has 981 source and 981 translated records;
- static export verifies 981 records.

If GitHub Pages publishing is performed, verify:

```bash
cd dist/amm-analysis-training
OWNER=$(gh api user --jq .login)
python3 - <<'PY'
from urllib.request import urlopen
import subprocess
owner = subprocess.check_output(["gh", "api", "user", "--jq", ".login"], text=True).strip()
url = f"https://{owner}.github.io/amm-analysis-training/"
with urlopen(url, timeout=60) as response:
    body = response.read().decode("utf-8", errors="replace")
print(url, response.status, len(body), "AMM Analysis Training" in body)
PY
```

Expected: status `200`, page contains `AMM Analysis Training`.
