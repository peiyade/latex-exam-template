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
GENERATED_OUTPUT_ENTRIES = ("docs", "source", "tools", "README.md")
PUBLIC_REPOSITORY_URL = "https://github.com/peiyade/amm-analysis-training"
ASSET_VERSION = "20260629-mobile-reader-mode"


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
    yaml_file = f"{record['id'].split('.')[-1]}.yaml"
    return {
        "id": record["id"],
        "source_id": source.get("translation_of", ""),
        "yaml_file": yaml_file,
        "github_source_url": f"{PUBLIC_REPOSITORY_URL}/blob/main/source/bank-yaml/{yaml_file}",
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

    prepare_output_root(output_root)
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


def prepare_output_root(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for entry in GENERATED_OUTPUT_ENTRIES:
        target = output_root / entry
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()


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
    docs_root = output_root / "docs"
    assets_root = docs_root / "assets"
    docs_root.mkdir(parents=True, exist_ok=True)
    assets_root.mkdir(parents=True, exist_ok=True)
    (docs_root / ".nojekyll").write_text("", encoding="utf-8")
    (docs_root / "index.html").write_text(INDEX_HTML.replace("__ASSET_VERSION__", ASSET_VERSION), encoding="utf-8")
    (assets_root / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (assets_root / "site.js").write_text(SITE_JS, encoding="utf-8")


def write_readme(output_root: Path, stats: Dict[str, Any]) -> None:
    (output_root / "README.md").write_text(
        "# AMM Analysis Training\n\n"
        "Static GitHub Pages site for the AMM analysis / inequality / extremum training bank.\n\n"
        f"Records: {stats['total']}\n",
        encoding="utf-8",
    )


def summarize_for_cli(summary: Dict[str, Any]) -> Dict[str, Any]:
    stats = summary.get("stats", {})
    return {
        "records": summary.get("records"),
        "output_root": summary.get("output_root"),
        "domains": stats.get("domains", {}),
        "priorities": stats.get("priorities", {}),
        "review_flags": stats.get("review_flags", {}),
    }


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AMM Analysis Training</title>
  <link rel="stylesheet" href="assets/site.css?v=__ASSET_VERSION__">
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
  <script defer src="assets/site.js?v=__ASSET_VERSION__"></script>
</head>
<body>
  <div class="site-shell">
    <header class="masthead">
      <div class="brand-block">
        <p class="eyebrow">AMM Analysis / Inequality / Extremum</p>
        <h1>模式识别训练题库</h1>
      </div>
      <div class="stats" id="stats" aria-label="题库统计"></div>
    </header>

    <main class="layout" aria-label="AMM 训练资料站">
      <aside class="filter-panel" aria-label="筛选">
        <div class="panel-title">
          <span>Filter</span>
          <button id="clear-filters" class="ghost-button" type="button">清除</button>
        </div>

        <label class="search-label" for="search-input">搜索</label>
        <input id="search-input" type="search" aria-label="题号、tag、方法、关键词" autocomplete="off">

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

        <div class="facet-strip" id="active-facets" aria-live="polite"></div>
      </aside>

      <section class="index-panel" aria-label="题目索引">
        <div class="index-head">
          <div>
            <p class="kicker">Index</p>
            <strong id="result-count">0</strong>
          </div>
          <div id="reader-summary" class="reader-summary"></div>
        </div>
        <nav id="question-list" class="question-list" aria-label="题目列表"></nav>
      </section>

      <article id="question-detail" class="reader-panel" aria-live="polite">
        <header id="reader-tools" class="reader-toolbar">
          <button id="back-to-list" class="toolbar-button" type="button">索引</button>
          <button id="prev-question" class="toolbar-button" type="button">上一题</button>
          <button id="next-question" class="toolbar-button" type="button">下一题</button>
          <button id="copy-link-button" class="toolbar-button accent" type="button">复制链接</button>
          <a id="source-link" class="toolbar-link" target="_blank" rel="noopener">YAML</a>
        </header>
        <div id="reader-content" class="reader-content"></div>
      </article>
    </main>
  </div>
  <script type="application/json" id="site-data-src">data/questions.json</script>
</body>
</html>
"""


SITE_CSS = r""":root {
  --ink: #20251f;
  --muted: #687068;
  --paper: #fbfaf4;
  --paper-deep: #f0eee4;
  --line: #d1cbb9;
  --line-dark: #a9b7ae;
  --green: #0b665c;
  --green-soft: #dceae4;
  --blue: #284a73;
  --rust: #8f3f2c;
  --shadow: 0 18px 45px rgba(32, 37, 31, 0.09);
  --ui-font: "Avenir Next", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --serif-font: "Iowan Old Style", "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background:
    linear-gradient(90deg, rgba(32, 37, 31, 0.035) 1px, transparent 1px),
    linear-gradient(0deg, rgba(32, 37, 31, 0.03) 1px, transparent 1px),
    var(--paper-deep);
  background-size: 46px 46px;
  font-family: var(--serif-font);
}
.site-shell { min-height: 100vh; }
.masthead {
  display: flex;
  justify-content: space-between;
  gap: 28px;
  padding: 22px 32px 18px;
  border-bottom: 2px solid var(--ink);
  background: rgba(251, 250, 244, 0.95);
}
.brand-block { min-width: 0; }
.eyebrow, .kicker {
  margin: 0 0 5px;
  color: var(--green);
  font: 800 13px/1.1 var(--ui-font);
}
h1 {
  margin: 0;
  font-size: 36px;
  line-height: 1.02;
}
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  align-content: start;
}
.layout {
  display: grid;
  grid-template-columns: minmax(250px, 320px) minmax(330px, 430px) minmax(560px, 1fr);
  gap: 16px;
  padding: 16px;
  min-height: calc(100vh - 98px);
}
.filter-panel, .index-panel, .reader-panel {
  min-width: 0;
  background: rgba(251, 250, 244, 0.96);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.filter-panel {
  position: sticky;
  top: 16px;
  height: calc(100vh - 130px);
  overflow: auto;
  padding: 16px;
}
.panel-title, .index-head, .reader-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.panel-title {
  border-bottom: 1px solid var(--line);
  padding-bottom: 12px;
  margin-bottom: 14px;
  font: 900 18px/1 var(--ui-font);
}
.filter-panel h2 {
  margin: 20px 0 8px;
  color: var(--muted);
  font: 800 13px/1.1 var(--ui-font);
  text-transform: uppercase;
}
.search-label {
  display: block;
  margin-bottom: 7px;
  color: var(--muted);
  font: 800 13px/1.1 var(--ui-font);
}
input, select, button {
  border: 1px solid var(--line-dark);
  background: var(--paper);
  color: var(--ink);
  border-radius: 0;
  padding: 9px 10px;
  font: 800 14px/1.2 var(--ui-font);
}
input, select { width: 100%; }
button { cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: 0.42; }
.ghost-button {
  width: auto;
  color: var(--green);
  background: transparent;
}
.chip-row, .facet-strip, .question-meta, .tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.chip, .badge, .stat-pill, .facet {
  width: auto;
  border: 1px solid var(--line-dark);
  background: var(--paper);
  color: var(--ink);
  padding: 5px 8px;
  font: 800 12px/1.1 var(--ui-font);
}
.chip.is-active, .facet {
  background: var(--green);
  border-color: var(--green);
  color: var(--paper);
}
.badge.domain-analysis { border-color: var(--blue); color: var(--blue); }
.badge.domain-inequality { border-color: var(--green); color: var(--green); }
.badge.domain-extremum { border-color: var(--rust); color: var(--rust); }
.stat-pill { font-size: 14px; background: var(--paper-deep); }
.facet-strip {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.index-panel {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 16px;
  height: calc(100vh - 130px);
}
.index-head {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 14px 14px 12px;
  border-bottom: 1px solid var(--line);
  background: var(--paper);
}
#result-count {
  display: block;
  font-size: 22px;
  line-height: 1.05;
}
.reader-summary {
  max-width: 220px;
  color: var(--muted);
  font: 800 12px/1.35 var(--ui-font);
  text-align: right;
}
.question-list {
  overflow: auto;
  min-height: 0;
}
.question-card {
  display: block;
  width: 100%;
  color: inherit;
  text-align: left;
  text-decoration: none;
  border-bottom: 1px solid var(--line);
  background: transparent;
  padding: 13px 14px 14px;
}
.question-card:hover { background: #f3f5ee; }
.question-card.is-selected {
  background: var(--green-soft);
  box-shadow: inset 4px 0 0 var(--green);
}
.question-card:focus-visible {
  outline: 3px solid var(--green);
  outline-offset: -3px;
}
.index-card .question-title {
  margin: 0 0 7px;
  font-size: 18px;
  font-weight: 900;
  line-height: 1.22;
}
.question-summary {
  color: var(--muted);
  font: 700 14px/1.5 var(--ui-font);
}
.reader-panel {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 16px;
  height: calc(100vh - 130px);
}
.reader-toolbar {
  position: sticky;
  top: 0;
  z-index: 3;
  justify-content: flex-end;
  flex-wrap: wrap;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  background: rgba(251, 250, 244, 0.96);
}
.toolbar-button, .toolbar-link {
  width: auto;
  min-height: 36px;
  border: 1px solid var(--line-dark);
  background: var(--paper);
  color: var(--ink);
  padding: 9px 11px;
  text-decoration: none;
  font: 900 13px/1 var(--ui-font);
}
.toolbar-button.accent {
  background: var(--ink);
  border-color: var(--ink);
  color: var(--paper);
}
.toolbar-link { display: inline-flex; align-items: center; }
.reader-content {
  overflow: auto;
  padding: 28px 32px 34px;
}
.question-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--ink);
}
.question-hero h2 {
  margin: 0;
  font-size: 38px;
  line-height: 1.08;
}
.source-stamp {
  color: var(--muted);
  font: 800 13px/1.6 var(--ui-font);
  text-align: right;
}
.detail-section {
  border-top: 1px solid var(--line);
  padding-top: 20px;
  margin-top: 24px;
}
.detail-section:first-of-type { border-top: 0; }
.detail-section h3 {
  margin: 0 0 10px;
  color: var(--green);
  font: 900 18px/1.2 var(--ui-font);
}
.latex-block {
  overflow-x: auto;
  white-space: pre-wrap;
  font-size: 19px;
  line-height: 1.88;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.info-card {
  border: 1px solid var(--line);
  background: #f5f6ef;
  padding: 13px;
}
.info-card strong {
  display: block;
  margin-bottom: 7px;
  color: var(--muted);
  font: 900 12px/1.1 var(--ui-font);
  text-transform: uppercase;
}
.info-card span, .info-card li {
  font-size: 16px;
  line-height: 1.6;
}
.info-card ul { margin: 0; padding-left: 18px; }
.source-block {
  color: var(--muted);
  font: 800 14px/1.75 var(--ui-font);
}
.source-block a {
  color: var(--blue);
  text-decoration: underline;
  text-underline-offset: 3px;
}
pre.tikz-source {
  overflow-x: auto;
  white-space: pre-wrap;
  padding: 12px;
  border: 1px solid var(--line-dark);
  background: #eef3ef;
  font-size: 13px;
}
@media (max-width: 1180px) {
  .layout { grid-template-columns: 300px 1fr; }
  .index-panel, .reader-panel { position: static; height: auto; }
  .reader-panel { grid-column: 1 / -1; min-height: 72vh; }
  .filter-panel { height: auto; position: static; }
}
@media (max-width: 760px) {
  .masthead { display: block; padding: 18px; }
  .stats { justify-content: flex-start; margin-top: 12px; }
  h1 { font-size: 30px; }
  .layout { display: block; padding: 10px; }
  .filter-panel, .index-panel, .reader-panel { margin-bottom: 12px; }
  body:not(.reader-open) .reader-panel { display: none; }
  body.reader-open .filter-panel,
  body.reader-open .index-panel { display: none; }
  body.reader-open .reader-panel {
    display: flex;
    min-height: calc(100vh - 96px);
  }
  .reader-toolbar { justify-content: flex-start; }
  .reader-content { padding: 22px 18px 28px; }
  .question-hero { display: block; }
  .question-hero h2 { font-size: 28px; }
  .source-stamp { text-align: left; margin-top: 12px; }
  .detail-grid { grid-template-columns: 1fr; }
  .reader-summary { max-width: none; text-align: left; }
}
"""


SITE_JS = r"""const state = {
  questions: [],
  filtered: [],
  selectedId: "",
  search: "",
  domain: "",
  priority: "",
  review: "",
  tag: "",
  method: "",
  readerOpen: false
};

document.addEventListener("DOMContentLoaded", async () => {
  const response = await fetch("data/questions.json");
  state.questions = await response.json();
  state.questions.sort((a, b) => String(a.problem_number || "").localeCompare(String(b.problem_number || "")) || a.id.localeCompare(b.id));
  renderStats();
  hydrateControls();
  const initialHashState = parseHash();
  Object.assign(state, initialHashState);
  setReaderMode(Boolean(initialHashState.selectedId));
  syncControlsFromState();
  applyFilters();
});

window.addEventListener("popstate", restoreStateFromHash);
window.addEventListener("hashchange", restoreStateFromHash);

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

function restoreStateFromHash() {
  const hashState = parseHash();
  Object.assign(state, hashState);
  setReaderMode(Boolean(hashState.selectedId));
  syncControlsFromState();
  applyFilters({ skipHash: true });
}

function setReaderMode(open) {
  state.readerOpen = Boolean(open);
  document.body.classList.toggle("reader-open", state.readerOpen);
}

function buildHash(selectedId = state.selectedId) {
  const params = new URLSearchParams();
  if (selectedId) params.set("q", selectedId);
  if (state.search) params.set("s", state.search);
  if (state.domain) params.set("domain", state.domain);
  if (state.priority) params.set("priority", state.priority);
  if (state.review) params.set("review", state.review);
  if (state.tag) params.set("tag", state.tag);
  if (state.method) params.set("method", state.method);
  return "#" + params.toString();
}

function questionHash(id) {
  return buildHash(id);
}

function writeHash(options = {}) {
  const hash = buildHash();
  if (window.location.hash === hash) return;
  const url = window.location.pathname + window.location.search + hash;
  if (options.push) {
    window.history.pushState(null, "", url);
  } else {
    window.history.replaceState(null, "", url);
  }
}

function renderStats() {
  const total = state.questions.length;
  const high = state.questions.filter(q => q.priority === "high").length;
  const cleanRequired = state.questions.filter(q => q.review_flag === "clean_required").length;
  document.getElementById("stats").innerHTML = [
    statPill(`${total} 题`),
    statPill(`High ${high}`),
    statPill(`Clean ${cleanRequired}`)
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
  document.getElementById("clear-filters").addEventListener("click", clearFilters);
  document.getElementById("prev-question").addEventListener("click", () => moveSelection(-1));
  document.getElementById("next-question").addEventListener("click", () => moveSelection(1));
  document.getElementById("copy-link-button").addEventListener("click", copyCurrentLink);
  document.getElementById("back-to-list").addEventListener("click", () => {
    setReaderMode(false);
    document.querySelector(".index-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function clearFilters() {
  state.search = "";
  state.domain = "";
  state.priority = "";
  state.review = "";
  state.tag = "";
  state.method = "";
  state.selectedId = "";
  setReaderMode(false);
  syncControlsFromState();
  applyFilters();
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

function applyFilters(options = {}) {
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
  renderActiveFacets();
  renderQuestionList();
  renderQuestion(state.questions.find(question => question.id === state.selectedId));
  renderReaderSummary();
  if (!options.skipHash) writeHash();
}

function renderActiveFacets() {
  const facets = [];
  if (state.search) facets.push(["search", state.search]);
  if (state.domain) facets.push(["domain", state.domain]);
  if (state.priority) facets.push(["priority", state.priority]);
  if (state.review) facets.push(["review", state.review]);
  if (state.tag) facets.push(["tag", state.tag]);
  if (state.method) facets.push(["method", state.method]);
  const container = document.getElementById("active-facets");
  if (!facets.length) {
    container.innerHTML = '<span class="badge">全部题目</span>';
    return;
  }
  container.innerHTML = facets.map(([field, value]) => `<button class="facet" type="button" data-field="${field}">${escapeHtml(value)}</button>`).join("");
  container.querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      state[button.dataset.field] = "";
      syncControlsFromState();
      applyFilters();
    });
  });
}

function renderReaderSummary() {
  const currentIndex = state.filtered.findIndex(question => question.id === state.selectedId);
  const summary = document.getElementById("reader-summary");
  if (currentIndex < 0) {
    summary.textContent = "";
    return;
  }
  summary.textContent = `${currentIndex + 1} / ${state.filtered.length}`;
}

function renderQuestionList() {
  document.getElementById("result-count").textContent = `${state.filtered.length} / ${state.questions.length}`;
  const list = document.getElementById("question-list");
  list.innerHTML = state.filtered.map(question => `
    <a class="question-card index-card ${question.id === state.selectedId ? "is-selected" : ""}" href="${questionHash(question.id)}" data-id="${escapeHtml(question.id)}" aria-current="${question.id === state.selectedId ? "true" : "false"}">
      <div class="question-title">${escapeHtml(question.problem_number || "")} · ${escapeHtml(question.title)}</div>
      <div class="question-meta">${badge(question.domain, `domain-${question.domain}`)}${badge(question.priority)}${badge(question.review_flag)}</div>
      <div class="question-summary">${escapeHtml(question.first_reaction || question.basic_judgment || "")}</div>
    </a>
  `).join("");
  list.querySelectorAll(".question-card").forEach(link => {
    link.addEventListener("click", event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      selectQuestion(link.dataset.id, { pushHistory: true, scrollDetail: true, revealIndex: false });
    });
  });
}

function selectQuestion(id, options = {}) {
  if (!id) return;
  state.selectedId = id;
  renderQuestionList();
  renderQuestion(state.questions.find(question => question.id === state.selectedId));
  renderReaderSummary();
  writeHash({ push: options.pushHistory });
  if (options.scrollDetail) setReaderMode(true);
  if (options.revealIndex !== false) ensureSelectedCardVisible();
  if (options.scrollDetail) scrollDetailIntoView();
}

function moveSelection(delta) {
  if (!state.filtered.length) return;
  const currentIndex = Math.max(0, state.filtered.findIndex(question => question.id === state.selectedId));
  const nextIndex = Math.min(state.filtered.length - 1, Math.max(0, currentIndex + delta));
  selectQuestion(state.filtered[nextIndex].id, { pushHistory: true, scrollDetail: true });
}

function renderQuestion(question) {
  const content = document.getElementById("reader-content");
  const sourceLink = document.getElementById("source-link");
  const previous = document.getElementById("prev-question");
  const next = document.getElementById("next-question");
  if (!question) {
    content.innerHTML = '<p class="empty-state">没有匹配的题目。</p>';
    sourceLink.removeAttribute("href");
    previous.disabled = true;
    next.disabled = true;
    return;
  }
  const currentIndex = state.filtered.findIndex(item => item.id === question.id);
  previous.disabled = currentIndex <= 0;
  next.disabled = currentIndex < 0 || currentIndex >= state.filtered.length - 1;
  sourceLink.href = githubSourceLink(question);
  sourceLink.textContent = question.yaml_file || "YAML";
  content.innerHTML = `
    <header class="question-hero">
      <div>
        <p class="kicker">${escapeHtml(question.domain)} / ${escapeHtml(question.priority)} / ${escapeHtml(question.review_flag)}</p>
        <h2>${escapeHtml(question.problem_number || "")} · ${escapeHtml(question.title)}</h2>
      </div>
      <div class="source-stamp">
        <div>${escapeHtml(question.legacy_id || question.id)}</div>
        <div>${escapeHtml(question.translation_review_status || question.status || "")}</div>
      </div>
    </header>
    <section class="detail-section">
      <h3>题干</h3>
      <div class="latex-block">${renderLatexText(question.stem_latex)}</div>
    </section>
    <section class="detail-section">
      <h3>模式识别</h3>
      <div class="detail-grid">
        ${infoCard("第一反应", question.first_reaction || question.basic_judgment)}
        ${infoCard("关键变换", question.key_transformation)}
        ${infoCard("训练用途", question.training_use)}
        ${infoCard("通用模板", question.general_template)}
      </div>
      <div class="tag-list">${[...question.tags, ...question.methods].map(value => badge(value)).join("")}</div>
    </section>
    <section class="detail-section">
      <h3>解答</h3>
      <div class="latex-block">${renderLatexText(question.solution_latex || "暂无解答。")}</div>
    </section>
    <section class="detail-section">
      <h3>风险与来源</h3>
      <div class="detail-grid">
        ${listBlock("常见陷阱", question.common_traps)}
        ${listBlock("数据质量", question.data_quality_flags)}
      </div>
      <div class="source-block">
        <div>id: ${escapeHtml(question.id)}</div>
        <div>source: ${escapeHtml(question.source_id)}</div>
        <div>legacy: ${escapeHtml(question.legacy_id || "")}</div>
        <div>model: ${escapeHtml(question.translation_model || "")}</div>
        <div>yaml: <a href="${escapeHtml(githubSourceLink(question))}" target="_blank" rel="noopener">${escapeHtml(question.yaml_file || "")}</a></div>
      </div>
    </section>
  `;
  content.scrollTop = 0;
  typesetMath();
}

function githubSourceLink(question) {
  return question.github_source_url || "#";
}

function copyCurrentLink() {
  const button = document.getElementById("copy-link-button");
  const text = window.location.href;
  const done = () => {
    button.textContent = "已复制";
    window.setTimeout(() => { button.textContent = "复制链接"; }, 1200);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}

function fallbackCopy(text, done) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
  done();
}

function ensureSelectedCardVisible() {
  document.querySelector(".question-card.is-selected")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function scrollDetailIntoView() {
  const detail = document.getElementById("question-detail");
  if (!detail) return;
  if (window.matchMedia("(max-width: 760px)").matches) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else if (window.matchMedia("(max-width: 1180px)").matches) {
    detail.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function infoCard(title, value) {
  return `<div class="info-card"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(value || "—")}</span></div>`;
}

function listBlock(title, values) {
  if (!values || !values.length) return infoCard(title, "—");
  return `<div class="info-card"><strong>${escapeHtml(title)}</strong><ul>${values.map(value => `<li>${escapeHtml(value)}</li>`).join("")}</ul></div>`;
}

function renderLatexText(text) {
  if (!text) return "";
  const html = `<div>${escapeHtml(text)}</div>`;
  if (text.includes("tikzpicture")) {
    return html + `<pre class="tikz-source">${escapeHtml(text)}</pre>`;
  }
  return html;
}

function typesetMath() {
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise([document.getElementById("reader-content")]).catch(console.error);
  }
}

function statPill(text) {
  return `<span class="stat-pill">${escapeHtml(String(text || ""))}</span>`;
}

function badge(text, extraClass = "") {
  return `<span class="badge ${escapeHtml(extraClass)}">${escapeHtml(String(text || ""))}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
"""


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
    print(json.dumps(summarize_for_cli(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
