# AMM Analysis Training Reference

This note records the current state of the AMM analysis / inequality / extremum training-bank project for later reference.

## Current Status

- Public site: https://peiyade.github.io/amm-analysis-training/
- Public repository: https://github.com/peiyade/amm-analysis-training
- Main working branch: `codex/amm-static-pages-site`
- Published repository branch: `main`
- Records exported: 981
- Domain counts: `analysis` 609, `inequality` 313, `extremum` 59
- Priority counts: `high` 654, `medium` 308, `low` 19
- Review flags: `auto_ok` 343, `needs_review` 272, `clean_required` 366

## Purpose

The project is a reference and training site for studying analysis, inequalities, and extremum problems through pattern recognition. The viewer is meant for reading and discussion, not as the source editor.

The useful learning layer is the metadata around each problem:

- `main_domain`
- `priority_for_course`
- `review_flag`
- `structure_tags`
- `candidate_methods`
- `basic_judgment`
- `training_card`

These fields are the bridge from a problem statement to "what structure should I recognize, and what methods become available?"

## Source Of Truth

The YAML bank remains the source of truth.

```text
bank/_curated/amm_analysis_training_full_zh/
bank/_curated/amm_analysis_training_full_source/
analysis/amm_analysis_training_full_audit.json
analysis/amm_analysis_training_full_manifest.json
```

The static site is generated from those files into:

```text
dist/amm-analysis-training/
```

That directory is also a separate Git repository for the public Pages site.

## Rebuild Commands

From the working repository:

```bash
python3 tools/build_static_amm_site.py --output-root dist/amm-analysis-training
```

Run the focused test suite:

```bash
python3 -m pytest tests/test_build_static_amm_site.py -q
```

Preview locally:

```bash
python3 -m http.server 8013 --directory dist/amm-analysis-training/docs
```

Then open:

```text
http://127.0.0.1:8013/
```

Publish the generated site:

```bash
git -C dist/amm-analysis-training status
git -C dist/amm-analysis-training add docs source tools README.md
git -C dist/amm-analysis-training commit -m "Update AMM training site"
git -C dist/amm-analysis-training push origin main
```

## Viewer Behavior

- Desktop uses a three-column reference layout: filters, index, reader.
- Mobile uses two states: index mode and reader mode. Selecting a problem opens the reader directly instead of scrolling past the full index.
- URL hash state is shareable. Example:

```text
https://peiyade.github.io/amm-analysis-training/#q=imported.amm_analysis_training_full_zh.p10337
```

## Known Boundaries

- `clean_required` records should be checked manually before classroom use.
- Translation quality is useful for reference but not final publication quality across all records.
- MathJax handles the math display; TikZ is intentionally treated as source fallback.
- The public viewer is not an editor, audit system, or worksheet generator.

## Recommended Next Pass

1. Filter `priority=high` and `review_flag=clean_required`.
2. Manually polish high-value questions first.
3. Strengthen `structure_tags`, `candidate_methods`, and `training_card` fields where the pattern-recognition value is weak.
4. Use the public viewer as the reading/review interface; update YAML only in the source bank.
