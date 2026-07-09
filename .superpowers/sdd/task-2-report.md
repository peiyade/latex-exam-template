# Task 2 Report: Deterministic Rule Checkers

## Status
DONE

## Summary
Implemented `tools/quality_checks.py` with deterministic rule checkers for schema, type consistency, LaTeX text, known bad patterns, content completeness, review state, and a batch runner.

Added `tests/test_quality_checks.py` to cover the required behaviors and verify the checker API.

## Commit
- `fc055a4` Add deterministic quality checks

## Tests
- `python3 -m pytest tests/test_quality_checks.py -q` -> 9 passed
- `python3 -m pytest tests/test_audit_amm_training_bank.py tests/test_question_loader.py -q` -> 6 passed

## Concerns
None

## Review Fix Update

### Review findings addressed
- Guarded nested `choices` and `answers` handling in `tools/quality_checks.py` so scalar or otherwise malformed entries now produce explicit high-severity issues instead of raising `AttributeError`.
- Added `type.choice_malformed_choice` and `type.fillin_malformed_answer` reporting for malformed nested items while leaving valid record behavior unchanged.
- Updated `fillin` consistency logic so answers without any `\blank{...}` markers now trigger `type.fillin_blank_answer_mismatch` with high severity.
- Made `latex_fields()` skip malformed nested items instead of crashing.

### Tests run
- `python3 -m pytest tests/test_quality_checks.py -q` -> `13 passed in 0.02s`
- `python3 -m pytest tests/test_audit_amm_training_bank.py tests/test_question_loader.py -q` -> `6 passed in 0.73s`

### Files changed
- `tools/quality_checks.py`
- `tests/test_quality_checks.py`
