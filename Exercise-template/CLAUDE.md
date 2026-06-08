# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Tsinghua University LaTeX exam template (adapted from USTBExam) with a Python automation toolchain that splits `.tex` exam papers into per-question images for online teaching platforms like 学习通 (Xuexitong) and 雨课堂.

## Key Commands

### One-click generation (most common)

```bash
# Mobile-optimized (~600px, 150 DPI) for 学习通 — the daily driver
python3 tools/generate_xt.py 2025-2026-Exercise-3

# General purpose with custom params
python3 tools/generate_all.py -f demo -w 600 --dpi 150

# Full pipeline: parse → PDF → PNG
python3 tools/generate_all.py -f 2025-2026-Exercise-3 -w 1000 --dpi 300
```

### Individual steps

```bash
# Compile .tex to PDF only (generates with/without answer versions)
python3 tools/compiler.py demo

# Generate per-component PDFs from a parsed .tex file
python3 tools/pdf_generator.py -f demo -w 800

# Convert all PDFs in a directory to PNG
python3 tools/pdf_to_png.py -i output/pdfs -o output/images --dpi 300
```

### LaTeX compilation (Overleaf/manual)

- Use **xeLaTeX** compiler (required for Chinese support)
- `\documentclass[answer]{THUExam}` renders answers in red; omit `answer` to hide them
- Source `.tex` files live in `examples/` or project root

## Architecture

```
.tex source
    │
    ▼
parser.py ─── Regex-based LaTeX parser
    │          Extracts: problem body, solution, note environments
    │          Classifies: CHOICE (pickout + options), FILLIN (\fillin{}), SOLUTION
    │
    ▼
pdf_generator.py ─── Wraps each component in standalone LaTeX → compiles to PDF
    │                 Uses local xelatex from PATH
    │
    ▼
pdf_to_png.py ─── Batch converts PDFs to PNG via pdftoppm (poppler)
```

### Data flow

- `parser.py` defines `Problem` dataclass with typed fields for each question type
- `ProblemType` enum: `CHOICE`, `FILLIN`, `SOLUTION`, `UNKNOWN`
- Each `Problem` carries: `body`, `body_clean` (answers stripped), `note`, `solution`, plus type-specific fields (`choice_answer`, `choice_options`, `fillin_answers`)
- `pdf_generator.py` and `image_generator.py` both consume parsed `Problem` objects and produce per-component standalone documents

### LaTeX class design

- `THUExam.cls`: Custom document class based on `ctexart`, provides `problem`, `solution`, `note`, `proof` environments
- `\fillin{...}` renders as underlined blank (student) or revealed answer (answer mode)
- `\pickout{X}` / `\pickin{X}` mark multiple-choice answers
- `\options{A}{B}{C}{D}` lays out 4 choice options with auto-formatting
- `\makepart{title}{scoring}` creates section headers (填空题, 解答题, etc.)
- `HTNotes-math.sty`: Math notation shortcuts (`\dif`, `\upe`, `\le` → `\leqslant`, etc.)

## Dependencies

- **Local XeLaTeX** (`xelatex` in PATH; TeX Live / MacTeX)
- **poppler** (`pdftoppm`): `brew install poppler` (macOS) or `apt-get install poppler-utils` (Ubuntu)
- Python stdlib only — no external pip packages required

## Input/Output conventions

- Source files: `examples/<name>.tex` or `<project_root>/<name>.tex`
- Output: `output/<name>/pdfs/` and `output/<name>/images/`
- Naming pattern: `{题型}{编号}{组件}.png` (e.g., `选择题1题干_C.png`, `填空题2答案1.png`, `计算题3笔记.png`)

## Known limitations

- `tools/parser.py` uses regex for LaTeX parsing, which struggles with deeply nested structures. The readme's TODO suggests `pylatexenc.latexwalker` as a potential replacement if parsing becomes too complex to maintain.
