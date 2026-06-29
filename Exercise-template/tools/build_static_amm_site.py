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
    docs_root = output_root / "docs"
    assets_root = docs_root / "assets"
    docs_root.mkdir(parents=True, exist_ok=True)
    assets_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
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


SITE_CSS = r"""* { box-sizing: border-box; }
body {
  margin: 0;
  color: #1f2421;
  background: #edf2ef;
  font-family: Georgia, "Noto Serif SC", "Source Han Serif SC", serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 32px 18px;
  border-bottom: 1px solid #b8c8c0;
  background: #fbfcf8;
}
.eyebrow { margin: 0 0 6px; color: #0a665a; font-weight: 700; }
h1 { margin: 0; font-size: 32px; line-height: 1.05; }
.stats { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; align-content: start; }
.stat-pill, .badge, .chip {
  border: 1px solid #b8c8c0;
  background: #fbfcf8;
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
  background: #fbfcf8;
  border: 1px solid #b8c8c0;
  min-width: 0;
}
.sidebar { padding: 16px; position: sticky; top: 16px; height: calc(100vh - 137px); overflow: auto; }
.sidebar h2 { font-size: 14px; margin: 18px 0 8px; color: #52615b; }
.search-label { display: block; font-weight: 700; margin-bottom: 8px; }
input, select, button {
  width: 100%;
  border: 1px solid #b8c8c0;
  background: #fbfcf8;
  color: #1f2421;
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
  border-bottom: 1px solid #b8c8c0;
  background: #fbfcf8;
}
.result-head button { width: auto; }
.question-card {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  border-bottom: 1px solid #d5dfda;
  background: transparent;
  padding: 14px 12px;
  cursor: pointer;
}
.question-card.is-selected { background: #e2eee9; box-shadow: inset 3px 0 0 #0a665a; }
.question-title { font-size: 18px; font-weight: 800; line-height: 1.2; margin-bottom: 7px; }
.question-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 7px; }
.question-summary { color: #52615b; font-size: 14px; line-height: 1.45; }
.detail { padding: 24px 28px; overflow: auto; }
.detail h2 { font-size: 34px; line-height: 1.08; margin: 0 0 12px; }
.detail-section { border-top: 1px solid #b8c8c0; padding-top: 18px; margin-top: 20px; }
.detail-section h3 { margin: 0 0 10px; color: #0a665a; font-size: 18px; }
.latex-block { font-size: 19px; line-height: 1.85; overflow-x: auto; white-space: pre-wrap; }
.card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.info-card { border: 1px solid #b8c8c0; padding: 12px; background: #f6f9f7; }
.info-card strong { display: block; margin-bottom: 6px; color: #52615b; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.source-block { color: #52615b; font-size: 14px; line-height: 1.6; }
pre.tikz-source { white-space: pre-wrap; overflow-x: auto; padding: 12px; background: #eef4f2; border: 1px solid #b8c8c0; }
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
  const html = `<div>${escapeHtml(text)}</div>`;
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
