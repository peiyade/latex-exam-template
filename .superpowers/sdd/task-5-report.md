# Task 5 Report: CLI Orchestration

Implemented the end-to-end `quality_audit` CLI in `tools/quality_audit.py` and added coverage in `tests/test_quality_audit_cli.py`.

What changed:
- Added `parse_args(argv: list[str] | None = None) -> argparse.Namespace`
- Added `run_audit(args: argparse.Namespace) -> int`
- Added `main(argv: list[str] | None = None) -> int`
- Wired YAML loading, record filtering, rule checks, render checks, and report writing together
- Wrote the required `quality_audit.json`, `quality_audit.jsonl`, and `quality_audit.html` outputs
- Kept render mode support to exactly `off`, `sample`, and `full`
- Preserved the default bank, output directory, render mode, and failure threshold required by the brief

Verification:
- `python3 -m pytest tests/test_quality_audit_cli.py -q`
- `python3 -m pytest tests/test_quality_core.py tests/test_quality_checks.py tests/test_quality_render.py tests/test_quality_reports.py tests/test_quality_audit_cli.py -q`

Result:
- CLI tests pass
- Full quality test suite passes

## Review Fix Note

Review finding addressed:
- Scoped source-level parse issues to the active CLI filters so focused `--question-id` and `--include-status` runs no longer fail on unrelated YAML parse errors.

Tests run and exact results:
- `python3 -m pytest tests/test_quality_audit_cli.py -q` -> `5 passed in 0.03s`
- `python3 -m pytest tests/test_quality_core.py tests/test_quality_checks.py tests/test_quality_render.py tests/test_quality_reports.py -q` -> `27 passed in 0.04s`

Files changed:
- `tools/quality_audit.py`
- `tests/test_quality_audit_cli.py`

## Review Fix Note 3

Review finding addressed:
- Updated `_source_issue_matches_question_filter()` to use the bank-relative source path when resolving parse errors, so focused runs for `imported.demo.q002` keep `demo/q002.yaml` and flat `q002.yaml` but exclude unrelated siblings like `other/q002.yaml`.

Tests run and exact results:
- `python3 -m pytest tests/test_quality_audit_cli.py -q` -> `7 passed in 0.05s`
- `python3 -m pytest tests/test_quality_core.py tests/test_quality_checks.py tests/test_quality_render.py tests/test_quality_reports.py -q` -> `27 passed in 0.05s`

Files changed:
- `tools/quality_audit.py`
- `tests/test_quality_audit_cli.py`

## Review Fix Note 2

Review finding addressed:
- Restored source parse errors for focused `--question-id` runs by matching `source.yaml_parse_error` entries against the selected question id's final segment when the file never produced a parsed `question_id`.

Tests run and exact results:
- `python3 -m pytest tests/test_quality_audit_cli.py -q` -> `6 passed in 0.03s`
- `python3 -m pytest tests/test_quality_core.py tests/test_quality_checks.py tests/test_quality_render.py tests/test_quality_reports.py -q` -> `27 passed in 0.04s`

Files changed:
- `tools/quality_audit.py`
- `tests/test_quality_audit_cli.py`
