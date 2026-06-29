# AMM Static Pages Site Design

## Goal

Create a distributable GitHub Pages site for the completed AMM analysis / inequality / extremum training bank. The site should be convenient for colleagues to browse at any time through a `github.io` URL, while preserving the training-card metadata that makes the bank useful for pattern recognition.

The first version is not an editing or audit system. It is a static reference site with search, filtering, tags, source visibility, and clear review-status markers.

## Repository Model

Use a separate GitHub repository named `amm-analysis-training`.

The export repository should have this shape:

```text
amm-analysis-training/
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

GitHub Pages should publish from `main` branch, `/docs` directory:

```bash
gh repo create amm-analysis-training --public --source=. --remote=origin --push
gh api repos/:owner/amm-analysis-training/pages \
  -X POST \
  -f source.branch=main \
  -f source.path=/docs
```

If Pages already exists, the setup command should use `PATCH` instead of `POST`.

## Source Data

The site builder reads from the existing generated bank:

- Chinese bank: `bank/_curated/amm_analysis_training_full_zh`
- Curated source bank: `bank/_curated/amm_analysis_training_full_source`
- Manifest: `analysis/amm_analysis_training_full_manifest.json`
- Audit: `analysis/amm_analysis_training_full_audit.json`

The Chinese bank is the primary display source. The curated source bank is used for source links, provenance, and optional English/source comparison later.

Each exported question record should include:

- id and source id;
- AMM problem number and title/comment;
- `main_domain`, `priority_for_course`, `review_flag`;
- `structure_tags`, `candidate_methods`, `recognition_cues`;
- `first_reaction`, `key_transformation`, `solution_skeleton`, `common_traps`, `training_use`;
- `stem_latex`, `solution_latex`;
- source metadata and preview/original ids.

## Viewer Design

Use a single static app in `docs/index.html`. It loads `docs/data/questions.json` and renders everything client-side. This avoids generating hundreds of individual HTML pages and keeps GitHub Pages deployment simple.

The viewer should have:

- a top search bar for title, id, problem number, tags, and text;
- filter chips for `analysis`, `inequality`, `extremum`;
- filter chips for `high`, `medium`, `low`;
- filter chips for `auto_ok`, `needs_review`, `clean_required`;
- tag and method filters;
- a compact result list with title, tags, priority, and first reaction;
- a reading pane or detail view with full problem content.

The detail view should show:

- title and metadata;
- visible status badges;
- problem statement;
- pattern-recognition card;
- solution;
- common traps and data-quality notes;
- source/provenance block.

The page should keep state in the URL hash, for example:

```text
/#q=imported.amm_analysis_training_full_zh.p12403_2
/#domain=inequality&priority=high&tag=Karamata
```

This lets colleagues share filtered views and individual problems without a backend.

## Math Rendering

Use MathJax for LaTeX math. The static site can start with CDN MathJax for simplicity:

```html
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
```

If offline distribution becomes important, vendor MathJax into `docs/assets/vendor/` later.

TikZ should not be a hard dependency in the first version. If a record contains `tikzpicture`, display the TikZ source in a clearly styled block and optionally render it later with TikZJax. This keeps the site robust when TikZJax cannot handle a diagram.

## Design Style

The site should feel like a quiet mathematical reference tool:

- dense but readable layout;
- restrained palette;
- strong typographic hierarchy for题干 / 模式识别 / 解答;
- clear badges for priority and review flag;
- no marketing hero page;
- responsive two-pane layout on wide screens, stacked layout on mobile.

## Build Script

Add a builder script:

```text
tools/build_static_amm_site.py
```

Responsibilities:

1. Load and validate the 981 Chinese YAML records.
2. Normalize metadata into a compact JSON schema.
3. Copy optional source YAML and audit/manifest files.
4. Write `docs/index.html`, `docs/assets/site.css`, `docs/assets/site.js`.
5. Write `docs/data/questions.json` and `docs/data/stats.json`.
6. Print a summary: records exported, domain counts, priority counts, review-flag counts.

The builder should fail if:

- source count and translated count differ;
- any question lacks `stem_latex`;
- any required metadata field is missing;
- audit reports unresolved failures or format issues.

## GitHub Publishing Flow

After building the export directory:

1. Initialize or update the `amm-analysis-training` repository.
2. Commit generated site files.
3. Use `gh repo create` if the repository does not exist.
4. Push to GitHub.
5. Configure Pages to publish `/docs`.
6. Verify the public URL returns HTTP 200.

Expected public URL:

```text
https://<github-user>.github.io/amm-analysis-training/
```

## Verification

Before declaring the site ready:

- run the existing AMM audit;
- run builder self-checks;
- serve the generated `docs/` locally and check `index.html`;
- verify search/filter behavior with Playwright or a small browser test;
- verify MathJax renders a sample formula;
- verify at least one high-priority inequality problem, one analysis problem, and one `clean_required` problem open correctly;
- if GitHub publishing is performed, verify the deployed Pages URL.

## Non-Goals For Version 1

- online editing;
- login or permissions;
- server-side search;
- full TikZ rendering guarantee;
- PDF export;
- classroom worksheet generation;
- replacing the YAML bank as the source of truth.

The YAML bank remains the source of truth. The static site is a generated distribution artifact.
