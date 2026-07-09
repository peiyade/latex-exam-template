# Question Quality Audit Toolchain Design

## Goal

Build a reusable quality-audit toolchain for mathematical question banks. The toolchain should catch problems that make a question unsafe or unclear for publication: incomplete structure, broken LaTeX, rendering failures, known OCR artifacts, mixed-in unrelated text, and high-risk review states.

The first implementation targets YAML question records, especially:

```text
bank/_curated/amm_analysis_training_full_zh
```

The design must stay general enough to support legacy THUExam `.tex` sources later by adapting parsed `.tex` problems into the same normalized question model.

## First-Version Scope

Version 1 uses deterministic checks plus LaTeX rendering checks. It does not use model-based mathematical review as a gate.

Included:

- YAML bank loading and normalization.
- Rule-based structure, schema, LaTeX text, and content-risk checks.
- Optional LaTeX rendering checks through `xelatex`.
- JSON, JSONL, and HTML quality reports.
- Soft-gate exit behavior: high-risk issues fail the command; medium and low issues only appear in reports.
- Render-result caching by content hash.

Excluded from version 1:

- Automatic proof verification.
- Model-based semantic review.
- Editing records from the HTML report.
- Replacing the current YAML bank or AMM static site builder.
- Full visual screenshot comparison.

## Command

Add one primary entry point:

```bash
python3 tools/quality_audit.py \
  --bank bank/_curated/amm_analysis_training_full_zh \
  --output-dir analysis \
  --render-mode sample
```

Important options:

```text
--bank PATH                 YAML question directory to audit, default bank/_curated/amm_analysis_training_full_zh
--output-dir PATH           report output directory, default analysis
--render-mode off|sample|full
--sample-size INT           number of low-risk records to render in sample mode
--fail-on SEVERITY          default high
--include-status STATUS     optional repeated filter for record status
--question-id ID            optional repeated filter for focused reruns
--keep-render-workdir       preserve temporary render files for debugging
```

If `--bank` is omitted, the command audits the AMM Chinese training bank, writes reports under `analysis/`, and returns a non-zero exit code if any `critical` or `high` issue exists.

## Architecture

The toolchain has four layers.

### 1. Source Adapters

Adapters convert source material into a normalized `QuestionRecord`.

Version 1 adapter:

- `YamlBankAdapter`: reads generated YAML files with `question_loader.load_question_file`.

Future adapter:

- `LegacyTexAdapter`: uses `LaTeXParser` and `legacy_yaml_exporter` logic to convert `examples/*.tex` problems into the same normalized model.

Adapters should not perform quality decisions. They only load, normalize, and report hard read errors.

### 2. Normalized Model

Each record is represented with these fields:

```text
id
source_path
source_metadata
schema_version
status
type
stem_latex
choices
answers
explanation_latex
solution_latex
comment
metadata
```

Missing optional fields are normalized to empty values. Missing required fields become quality issues.

### 3. Checkers

Each checker receives one normalized record and returns zero or more `QualityIssue` objects.

Initial checkers:

- `SchemaChecker`
- `TypeConsistencyChecker`
- `LatexTextChecker`
- `KnownBadPatternChecker`
- `ContentCompletenessChecker`
- `ReviewStateChecker`
- `RenderChecker`

Checkers should be small and independently tested. They should not write files except for `RenderChecker`, which writes temporary `.tex` files and cache entries.

### 4. Reporters And Gate

Reporters consume all issues and write:

```text
analysis/quality_audit.json
analysis/quality_audit.jsonl
analysis/quality_audit.html
```

The gate then computes the worst severity and exits:

```text
critical or high issue present  => exit 1
medium and low issues only      => exit 0
no issues                       => exit 0
```

The default failing threshold is `high`.

## Issue Model

Each issue has:

```text
id                  stable issue id, e.g. latex.unclosed_environment
severity            critical|high|medium|low
question_id
field               stem_latex, solution_latex, choices[2].text_latex, etc.
message             human-readable summary
evidence            short excerpt or structured detail
source_path
source_line         if known
render_artifacts    optional paths for render errors
```

Severity meanings:

- `critical`: the record cannot be reliably loaded, understood, or rendered. Examples: YAML parse failure, missing `id`, missing `stem_latex`, LaTeX compilation failure in a required field.
- `high`: the record is likely unsafe for student-facing use. Examples: choice question has zero or multiple correct options, fill-in blanks and answers mismatch, solution contains unrelated AMM page headers or submission instructions, `review_flag=clean_required`.
- `medium`: manual review is needed but the question may still be usable. Examples: `review_flag=needs_review`, complex TikZ/table rendering risk, very short solution for a multi-part problem, unknown macro that does not break compilation.
- `low`: cleanup recommendation. Examples: missing nonessential comment, overly long comment, excessive blank lines, source metadata gaps.

## Rule Checks

### SchemaChecker

Checks:

- `id`, `type`, and `stem_latex` exist and are non-empty.
- `schema_version` exists for YAML records.
- `type` is one of `choice`, `fillin`, or `solution` in version 1. New types must be added to a named allowlist before they can pass schema checks.
- source metadata contains at least one provenance field such as `file`, `legacy_id`, or `translation_of`.

Severity:

- Missing `id`, `type`, or `stem_latex`: `critical`.
- Missing source metadata: `low`.
- Unknown type: `high`.

### TypeConsistencyChecker

Checks:

- `choice` records have a non-empty `choices` list.
- Choice records have exactly one `correct: true` choice unless the schema later explicitly supports multi-select.
- Choice keys are unique.
- `fillin` records have answer entries.
- If `stem_latex` contains `\blank{blankN}`, matching answer keys exist.
- `solution` records should have `solution_latex` or `explanation_latex` unless intentionally marked as statement-only.

Severity:

- Choice answer count not equal to one: `high`.
- Fill-in blank and answer mismatch: `high`.
- Missing solution on solution-type record: `medium`.

### LatexTextChecker

Checks all LaTeX-bearing fields:

- Balanced inline dollar delimiters.
- Balanced display delimiters `\[...\]` and `$$...$$`.
- Balanced `\begin{...}` and `\end{...}` environments.
- Common broken command patterns such as `\nmathbb`.
- JSON wrapper leakage such as `{"text": ...}`.
- Escaped linebreaks in text mode where they are likely translation artifacts.

Severity:

- Unbalanced math or environment delimiters: `critical`.
- Known broken command pattern: `high`.
- JSON wrapper leakage: `high`.
- Suspicious text-mode linebreak: `medium`.

### KnownBadPatternChecker

Detects text that is known to be unrelated to the question:

- AMM page headers such as `Problems and Solutions`.
- Editor names and contributor lists.
- Submission instructions.
- Next-section headings.
- OCR artifacts already seen in this repository.

Severity:

- Unrelated page/header material in `stem_latex` or `solution_latex`: `high`.
- Lower-confidence OCR artifact: `medium`.

### ContentCompletenessChecker

Uses deterministic heuristics, not mathematical proof.

Checks:

- If the stem has multiple parts such as `(a)`, `(b)`, `(c)`, the solution should mention corresponding parts or contain comparable structure.
- If the stem asks for a figure or diagram using text like `如下图`, the record should contain a TikZ block, image reference, or source note.
- If the solution is much shorter than the multi-part stem, flag it for review.

Severity:

- Clear multi-part mismatch: `high`.
- Weak evidence of incomplete coverage: `medium`.
- Missing figure reference: `medium`.

### ReviewStateChecker

Uses existing curation metadata:

```text
metadata.curation.review_flag
metadata.translation.review_status
status
```

Severity:

- `review_flag=clean_required`: `high`.
- `review_flag=needs_review`: `medium`.
- `status=machine_draft`: `low`, unless paired with stronger issues.

`auto_ok` does not skip other checks.

## Render Checking

Render checks compile a minimal standalone document with `xelatex`.

Fields included in one record-level render document:

- `stem_latex`
- choice option text
- fill-in answers
- `explanation_latex`
- `solution_latex`

The preamble should reuse the packages and conventions already present in `tools/pdf_generator.py`:

- `ctex` with `fontset=fandol`
- `amsmath`, `amssymb`, `unicode-math`
- `tikz`, `enumitem`, `array`, `tabularx`
- common math macros such as `\dif`, `\upe`, `\leqslant`, `\geqslant`

Render modes:

```text
off       no render checks
sample    render high-risk records plus a deterministic sample
full      render every loaded record
```

Sample mode selects:

- all records that already have `critical`, `high`, or render-relevant `medium` rule issues;
- records whose review state is `clean_required`;
- a deterministic sample of the remaining records sorted by id.

Render cache:

```text
analysis/quality_render_cache/
```

Cache key:

```text
sha256(tool_version + render_preamble + rendered_field_payload)
```

Cached result stores:

- success/failure
- return code
- log excerpt
- generated `.tex` path if preserved
- timestamp

Render failure severity:

- Required field compilation failure: `critical`.
- Timeout: `critical`.
- Missing local `xelatex`: one global `critical` issue if render mode is not `off`.
- Warnings without failure: `medium` or `low`, depending on pattern.

## Reports

### JSON

`analysis/quality_audit.json` contains:

- audit metadata: timestamp, command options, source path, render mode;
- summary counts by severity;
- counts by issue id;
- counts by source/status/review flag when available;
- full issue list.

### JSONL

`analysis/quality_audit.jsonl` contains one issue per line for easy filtering:

```bash
rg '"severity": "high"' analysis/quality_audit.jsonl
```

### HTML

`analysis/quality_audit.html` is a static review page.

It should include:

- severity filters;
- issue-id filters;
- review-flag filters;
- search by question id;
- grouped issue cards by question;
- links to existing local preview URLs when present;
- render log excerpts for compilation failures.

The HTML report is a reviewer aid, not an editor.

## Integration With Existing Tools

The new tool should reuse existing project code where possible:

- `question_loader.py` for YAML parsing.
- `legacy_yaml_exporter.py` for YAML output conventions in tests.
- `pdf_generator.py` preamble conventions for render checks.
- `audit_amm_training_bank.py` known format checks where they are still applicable.
- `html_preview_server.py` preview URLs when source metadata contains them.

The existing `tools/audit_amm_training_bank.py` can remain as the AMM translation/export audit. The new `quality_audit.py` is a broader publication-quality audit.

The static AMM site builder can later call or require `quality_audit.py` before publishing. Version 1 does not need to wire that gate into `build_static_amm_site.py`; it only needs a clear command that can be run before publication.

## Testing

Add focused tests for:

- required-field failures;
- choice answer count validation;
- fill-in blank/answer matching;
- LaTeX delimiter and environment matching;
- known bad AMM page-header patterns;
- review flag severity mapping;
- render cache key stability;
- render checker behavior with a fake subprocess runner;
- JSON and JSONL report shape;
- soft-gate exit status.

Avoid requiring a local TeX installation for the normal test suite. Tests should mock render subprocess calls. A separate manual command can exercise real `xelatex`.

## Migration Path For `.tex` Sources

After YAML auditing is stable, add:

```bash
python3 tools/quality_audit.py --tex examples/demo.tex --render-mode full
```

The `.tex` adapter should:

- parse problems with `LaTeXParser`;
- convert them to normalized records;
- preserve source line numbers;
- run the same checkers and reports;
- optionally reuse the existing per-question image generation output paths in report links.

This keeps the checker layer independent of whether questions came from YAML or THUExam `.tex`.

## Success Criteria

Version 1 is successful when:

- `quality_audit.py --render-mode off` runs on the AMM Chinese bank and writes all three reports.
- `quality_audit.py --render-mode sample` runs with cached render results and reports compile failures clearly.
- The command exits non-zero when injected high-risk fixtures are present.
- The normal test suite does not require TeX.
- Existing tests continue to pass.
- The design leaves a clear adapter path for legacy `.tex` sources.
