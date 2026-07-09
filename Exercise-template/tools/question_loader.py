#!/usr/bin/env python3
"""Load draft YAML questions into a small indexed question bank."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class QuestionBank:
    questions: List[Dict[str, Any]]

    def __post_init__(self) -> None:
        self._by_id = {question["id"]: question for question in self.questions}

    def get(self, question_id: str) -> Dict[str, Any]:
        return self._by_id[question_id]

    def list_sources(self) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for question in self.questions:
            slug = source_slug_from_question(question)
            grouped.setdefault(slug, []).append(question)

        sources = []
        for slug in sorted(grouped):
            questions = sorted(grouped[slug], key=lambda item: item["id"])
            sources.append(
                {
                    "slug": slug,
                    "count": len(questions),
                    "first_question_id": questions[0]["id"],
                }
            )
        return sources


def load_question_bank(root: Path) -> QuestionBank:
    yaml_files = sorted(Path(root).glob("**/*.yaml"))
    questions = [load_question_file(path) for path in yaml_files]
    questions.sort(key=lambda question: question["id"])
    return QuestionBank(questions)


def load_question_file(path: Path) -> Dict[str, Any]:
    question = parse_yaml_subset(path.read_text(encoding="utf-8"))
    question["_path"] = str(path)
    return question


def source_slug_from_question(question: Dict[str, Any]) -> str:
    question_id = question["id"]
    parts = question_id.split(".")
    if len(parts) >= 3 and parts[0] == "imported":
        return parts[1]
    source = question.get("source", {}).get("file", "unknown")
    return Path(source).stem


def parse_yaml_subset(text: str) -> Dict[str, Any]:
    """Parse the generated YAML subset used by bank/_imported.

    This is intentionally small: mappings, lists of mappings, inline scalar
    values, inline empty lists, and literal block scalars.
    """
    lines = text.splitlines()
    value, index = _parse_block(lines, 0, 0)
    if index < len(lines):
        raise ValueError(f"Unexpected YAML content at line {index + 1}")
    if not isinstance(value, dict):
        raise ValueError("Top-level YAML value must be a mapping")
    return value


def _parse_block(lines: List[str], index: int, indent: int) -> Tuple[Any, int]:
    index = _skip_empty(lines, index)
    if index >= len(lines):
        return {}, index
    stripped = lines[index][indent:].lstrip()
    if stripped.startswith("- "):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: List[str], index: int, indent: int) -> Tuple[Dict[str, Any], int]:
    result: Dict[str, Any] = {}
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        current_indent = _indent_of(lines[index])
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"Unexpected indentation at line {index + 1}")

        stripped = lines[index][indent:]
        if stripped.startswith("- "):
            break
        key, raw_value = _split_key_value(stripped, index)

        if raw_value == "|-":
            block, index = _parse_literal_block(lines, index + 1, indent + 2)
            result[key] = block
        elif raw_value == "":
            value, index = _parse_block(lines, index + 1, indent + 2)
            result[key] = value
        else:
            result[key] = _parse_scalar(raw_value)
            index += 1
    return result, index


def _parse_sequence(lines: List[str], index: int, indent: int) -> Tuple[List[Any], int]:
    result: List[Any] = []
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        current_indent = _indent_of(lines[index])
        if current_indent < indent:
            break
        if current_indent != indent:
            raise ValueError(f"Unexpected indentation at line {index + 1}")

        stripped = lines[index][indent:]
        if not stripped.startswith("- "):
            break
        item_text = stripped[2:]
        if item_text == "":
            value, index = _parse_block(lines, index + 1, indent + 2)
            result.append(value)
            continue
        if item_text == "|-":
            block, index = _parse_literal_block(lines, index + 1, indent + 2)
            result.append(block)
            continue
        if ": " in item_text or item_text.endswith(":"):
            key, raw_value = _split_key_value(item_text, index)
            item: Dict[str, Any] = {}
            if raw_value == "|-":
                block, index = _parse_literal_block(lines, index + 1, indent + 2)
                item[key] = block
            elif raw_value == "":
                value, index = _parse_block(lines, index + 1, indent + 2)
                item[key] = value
            else:
                item[key] = _parse_scalar(raw_value)
                index += 1

            while index < len(lines):
                if not lines[index].strip():
                    index += 1
                    continue
                next_indent = _indent_of(lines[index])
                if next_indent < indent + 2:
                    break
                if next_indent != indent + 2:
                    raise ValueError(f"Unexpected indentation at line {index + 1}")
                stripped_next = lines[index][indent + 2 :]
                if stripped_next.startswith("- "):
                    break
                next_key, next_raw_value = _split_key_value(stripped_next, index)
                if next_raw_value == "|-":
                    block, index = _parse_literal_block(lines, index + 1, indent + 4)
                    item[next_key] = block
                elif next_raw_value == "":
                    value, index = _parse_block(lines, index + 1, indent + 4)
                    item[next_key] = value
                else:
                    item[next_key] = _parse_scalar(next_raw_value)
                    index += 1
            result.append(item)
        else:
            result.append(_parse_scalar(item_text))
            index += 1
    return result, index


def _parse_literal_block(lines: List[str], index: int, indent: int) -> Tuple[str, int]:
    block_lines: List[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() and _indent_of(line) < indent:
            break
        if line.startswith(" " * indent):
            block_lines.append(line[indent:])
        else:
            block_lines.append("")
        index += 1
    return "\n".join(block_lines).rstrip(), index


def _split_key_value(text: str, index: int) -> Tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Expected key-value pair at line {index + 1}")
    key, raw_value = text.split(":", 1)
    return key.strip(), raw_value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if value.isdigit():
        return int(value)
    return value


def _skip_empty(lines: List[str], index: int) -> int:
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
