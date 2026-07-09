#!/usr/bin/env python3
"""Run publication-quality audits for structured question banks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quality_checks import run_rule_checks
from quality_core import DEFAULT_BANK, DEFAULT_OUTPUT_DIR, QuestionRecord, load_yaml_bank, should_fail
from quality_render import RenderOptions, run_render_checks
from quality_reports import write_reports


VALID_RENDER_MODES = ("off", "sample", "full")
VALID_SEVERITIES = ("low", "medium", "high", "critical")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit mathematical question-bank quality.")
    parser.add_argument(
        "--bank",
        type=Path,
        default=DEFAULT_BANK,
        help=f"YAML question directory (default: {DEFAULT_BANK})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Report output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--render-mode", choices=VALID_RENDER_MODES, default="sample")
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument("--fail-on", choices=VALID_SEVERITIES, default="high")
    parser.add_argument("--include-status", action="append", default=[])
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--keep-render-workdir", action="store_true")
    return parser.parse_args(argv)


def run_audit(args: argparse.Namespace) -> int:
    records, source_issues = load_yaml_bank(args.bank)
    records = _filter_records(records, args.include_status, args.question_id)
    source_issues = _filter_source_issues(source_issues, records, args.include_status, args.question_id)

    rule_issues = run_rule_checks(records)
    render_issues = run_render_checks(
        records,
        source_issues + rule_issues,
        RenderOptions(
            mode=args.render_mode,
            output_dir=args.output_dir,
            sample_size=args.sample_size,
            keep_workdir=args.keep_render_workdir,
        ),
    )
    issues = source_issues + rule_issues + render_issues

    report_paths = write_reports(
        records,
        issues,
        args.output_dir,
        {
            "source": str(args.bank),
            "render_mode": args.render_mode,
            "sample_size": args.sample_size,
            "fail_on": args.fail_on,
        },
    )
    _print_summary(records, issues, report_paths)
    return 1 if should_fail(issues, args.fail_on) else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_audit(args)


def _filter_records(
    records: list[QuestionRecord],
    statuses: list[str],
    question_ids: list[str],
) -> list[QuestionRecord]:
    selected = records
    if statuses:
        allowed_statuses = set(statuses)
        selected = [record for record in selected if record.status in allowed_statuses]
    if question_ids:
        allowed_ids = set(question_ids)
        selected = [record for record in selected if record.id in allowed_ids]
    return selected


def _filter_source_issues(
    issues,
    records: list[QuestionRecord],
    statuses: list[str],
    question_ids: list[str],
):
    if not statuses and not question_ids:
        return issues

    if question_ids:
        return [issue for issue in issues if _source_issue_matches_question_filter(issue, question_ids)]

    selected_ids = {record.id for record in records}
    if not selected_ids:
        return []

    return [issue for issue in issues if issue.question_id and issue.question_id in selected_ids]


def _source_issue_matches_question_filter(issue, question_ids: list[str]) -> bool:
    if issue.question_id and issue.question_id in question_ids:
        return True
    if not issue.source_path:
        return False

    source_stem = issue.source_path.stem
    return any(question_id.rsplit(".", 1)[-1] == source_stem for question_id in question_ids)


def _print_summary(records, issues, report_paths) -> None:
    counts = {}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    print(f"records: {len(records)}")
    print(f"issues: {len(issues)}")
    for severity in ("critical", "high", "medium", "low"):
        print(f"{severity}: {counts.get(severity, 0)}")
    print(f"json: {report_paths['json']}")
    print(f"jsonl: {report_paths['jsonl']}")
    print(f"html: {report_paths['html']}")


if __name__ == "__main__":
    sys.exit(main())
