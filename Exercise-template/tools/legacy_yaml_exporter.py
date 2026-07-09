#!/usr/bin/env python3
"""Export legacy THUExam LaTeX problems as draft YAML question files."""

import argparse
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from parser import LaTeXParser, Problem, ProblemType


CHOICE_LABELS = ["A", "B", "C", "D"]


def slugify_source(path: Path) -> str:
    """Create a stable source slug for imported question IDs."""
    return re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")


def problem_start_lines(tex_content: str) -> List[int]:
    """Return 1-based line numbers for legacy problem environments."""
    pattern = r"\\begin\{problem\}(.*?)\\end\{problem\}"
    return [tex_content.count("\n", 0, match.start()) + 1 for match in re.finditer(pattern, tex_content, re.DOTALL)]


def convert_legacy_tex_to_question_records(
    tex_content: str,
    source_file: str,
    source_slug: str,
) -> List[Dict[str, Any]]:
    """Convert one legacy TeX document into normalized draft question records."""
    parser = LaTeXParser(tex_content)
    problems = parser.parse()
    start_lines = problem_start_lines(tex_content)

    records = []
    for index, problem in enumerate(problems, 1):
        line = start_lines[index - 1] if index <= len(start_lines) else None
        records.append(
            convert_problem_to_record(
                problem=problem,
                source_file=source_file,
                source_slug=source_slug,
                problem_index=index,
                source_line=line,
            )
        )
    return records


def convert_problem_to_record(
    problem: Problem,
    source_file: str,
    source_slug: str,
    problem_index: int,
    source_line: Optional[int],
) -> Dict[str, Any]:
    """Convert one parsed legacy problem into a draft question record."""
    question_id = f"imported.{source_slug}.q{problem_index:03d}"
    record: Dict[str, Any] = {
        "schema_version": 1,
        "id": question_id,
        "status": "draft",
        "type": legacy_type_name(problem),
        "source": {
            "file": source_file,
            "legacy_id": f"{source_slug}#problem-{problem_index}",
        },
        "stem_latex": stem_for_problem(problem),
        "comment": comment_for_problem(problem),
    }

    if source_line is not None:
        record["source"]["line"] = source_line

    if problem.type == ProblemType.CHOICE:
        answer = (problem.choice_answer or "").strip().upper()
        record["choices"] = [
            {
                "key": f"opt{idx}",
                "text_latex": option.content,
                "correct": option.label.upper() == answer,
            }
            for idx, option in enumerate(problem.choice_options, 1)
        ]
    elif problem.type == ProblemType.FILLIN:
        record["answers"] = [
            {
                "key": f"blank{answer.index}",
                "latex": answer.content,
                "aliases": [],
            }
            for answer in problem.fillin_answers
        ]

    if problem.note:
        record["explanation_latex"] = problem.note
    if problem.solution:
        record["solution_latex"] = problem.solution

    return record


def legacy_type_name(problem: Problem) -> str:
    if problem.type == ProblemType.CHOICE:
        return "choice"
    if problem.type == ProblemType.FILLIN:
        return "fillin"
    return "solution"


def stem_for_problem(problem: Problem) -> str:
    if problem.type == ProblemType.FILLIN:
        return fillin_stem_with_semantic_blanks(problem.body)
    if problem.type == ProblemType.CHOICE:
        return problem.body_clean
    return problem.body


def comment_for_problem(problem: Problem, limit: int = 72) -> str:
    comment = stem_for_problem(problem)
    compact = re.sub(r"\s+", " ", comment).strip()
    if not compact:
        return "（暂无评论）"
    if len(compact) > limit:
        compact = compact[: limit - 1] + "…"
    return compact


def fillin_stem_with_semantic_blanks(body: str) -> str:
    """Replace legacy \\fillin{...} answers with semantic blank markers."""
    matches = LaTeXParser(body)._extract_nested_command(body, "fillin")
    stem = body
    for blank_index, (start, end, _) in enumerate(reversed(matches), 1):
        original_index = len(matches) - blank_index + 1
        stem = stem[:start] + rf"\blank{{blank{original_index}}}" + stem[end:]
    return stem.strip()


def write_records_to_directory(records: Iterable[Dict[str, Any]], output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for record in records:
        filename = record["id"].split(".")[-1] + ".yaml"
        (output_dir / filename).write_text(record_to_yaml(record), encoding="utf-8")
        count += 1
    return count


def record_to_yaml(record: Dict[str, Any]) -> str:
    return yaml_from_value(record).rstrip() + "\n"


def yaml_from_value(value: Any, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if should_use_block_scalar(key, item):
                lines.append(f"{spaces}{key}: |-")
                lines.extend(indent_block(str(item), indent + 2))
            elif item == []:
                lines.append(f"{spaces}{key}: []")
            elif isinstance(item, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(yaml_from_value(item, indent + 2))
            else:
                lines.append(f"{spaces}{key}: {yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{spaces}[]"
        lines = []
        for item in value:
            if isinstance(item, dict):
                item_lines = yaml_from_value(item, indent + 2).splitlines()
                lines.append(f"{spaces}- {item_lines[0].lstrip()}")
                lines.extend(item_lines[1:])
            elif is_block_scalar(item):
                lines.append(f"{spaces}- |-")
                lines.extend(indent_block(str(item), indent + 2))
            else:
                lines.append(f"{spaces}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{spaces}{yaml_scalar(value)}"


def should_use_block_scalar(key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if key.endswith("_latex") or key in {"latex", "text_latex", "stem_latex"}:
        return True
    return is_block_scalar(value)


def is_block_scalar(value: Any) -> bool:
    return isinstance(value, str) and ("\n" in value or "\\" in value or "$" in value or ":" in value)


def indent_block(text: str, indent: int) -> List[str]:
    spaces = " " * indent
    if text == "":
        return [spaces]
    return [spaces + line for line in text.splitlines()]


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if re.fullmatch(r"[A-Za-z0-9_.#/\-]+", text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def export_tex_file(source_file: Path, project_root: Path, output_root: Path) -> int:
    tex_content = source_file.read_text(encoding="utf-8")
    rel_source = source_file.relative_to(project_root).as_posix()
    source_slug = slugify_source(source_file)
    records = convert_legacy_tex_to_question_records(
        tex_content=tex_content,
        source_file=rel_source,
        source_slug=source_slug,
    )
    return write_records_to_directory(records, output_root / source_slug)


def collect_default_sources(project_root: Path) -> List[Path]:
    sources = []
    main_tex = project_root / "main.tex"
    if main_tex.exists():
        sources.append(main_tex)
    examples_dir = project_root / "examples"
    if examples_dir.exists():
        sources.extend(sorted(examples_dir.glob("*.tex")))
    return sources


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Export legacy THUExam .tex problems to draft YAML question files."
    )
    arg_parser.add_argument(
        "sources",
        nargs="*",
        help="Optional .tex files to export. Defaults to main.tex and examples/*.tex.",
    )
    arg_parser.add_argument(
        "-o",
        "--output",
        default="bank/_imported",
        help="Output directory for imported draft YAML files.",
    )
    args = arg_parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    output_root = (project_root / args.output).resolve()
    sources = [Path(source).resolve() for source in args.sources] if args.sources else collect_default_sources(project_root)

    total = 0
    for source in sources:
        count = export_tex_file(source, project_root, output_root)
        total += count
        print(f"{source.relative_to(project_root)}: exported {count} questions")
    print(f"Exported {total} questions to {output_root}")


if __name__ == "__main__":
    main()
