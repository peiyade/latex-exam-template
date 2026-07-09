import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def test_choice_problem_exports_structured_answer_and_explanation():
    from legacy_yaml_exporter import convert_legacy_tex_to_question_records

    tex = r"""
\begin{problem}
设函数 $f(x)$ 可导，则下列说法正确的是\pickout{C}
\options
{$f(x)$ 连续}
{$f'(x)$ 不存在}
{$f(x)$ 在该点连续}
{$f(x)$ 为常数}
\end{problem}
\begin{note}
可导必连续。
\end{note}
"""

    records = convert_legacy_tex_to_question_records(
        tex_content=tex,
        source_file="examples/demo.tex",
        source_slug="demo",
    )

    assert len(records) == 1
    record = records[0]
    assert record["id"] == "imported.demo.q001"
    assert record["type"] == "choice"
    assert record["stem_latex"] == r"设函数 $f(x)$ 可导，则下列说法正确的是"
    assert [choice["key"] for choice in record["choices"]] == [
        "opt1",
        "opt2",
        "opt3",
        "opt4",
    ]
    assert [choice["correct"] for choice in record["choices"]] == [
        False,
        False,
        True,
        False,
    ]
    assert record["explanation_latex"] == "可导必连续。"


def test_fillin_problem_exports_semantic_blank_and_answer():
    from legacy_yaml_exporter import convert_legacy_tex_to_question_records

    tex = r"""
\begin{problem}
计算 $\displaystyle\int_0^1 x^2\,\mathrm{d}x = $ \fillin{$\dfrac{1}{3}$}。
\end{problem}
"""

    records = convert_legacy_tex_to_question_records(
        tex_content=tex,
        source_file="examples/demo.tex",
        source_slug="demo",
    )

    assert len(records) == 1
    record = records[0]
    assert record["type"] == "fillin"
    assert record["stem_latex"] == (
        r"计算 $\displaystyle\int_0^1 x^2\,\mathrm{d}x = $ \blank{blank1}。"
    )
    assert record["answers"] == [
        {
            "key": "blank1",
            "latex": r"$\dfrac{1}{3}$",
            "aliases": [],
        }
    ]


def test_solution_problem_exports_solution_latex():
    from legacy_yaml_exporter import convert_legacy_tex_to_question_records

    tex = r"""
\begin{problem}
求函数 $f(x)=x^2$ 的导数。
\end{problem}
\begin{solution}
$f'(x)=2x$。
\end{solution}
"""

    records = convert_legacy_tex_to_question_records(
        tex_content=tex,
        source_file="examples/demo.tex",
        source_slug="demo",
    )

    assert len(records) == 1
    record = records[0]
    assert record["type"] == "solution"
    assert record["stem_latex"] == r"求函数 $f(x)=x^2$ 的导数。"
    assert record["solution_latex"] == r"$f'(x)=2x$。"


def test_yaml_output_uses_block_scalars_for_latex_fields_and_inline_empty_lists():
    from legacy_yaml_exporter import record_to_yaml

    yaml_text = record_to_yaml(
        {
            "schema_version": 1,
            "id": "imported.demo.q001",
            "explanation_latex": "一行解析。",
            "answers": [
                {
                    "key": "blank1",
                    "latex": r"$\dfrac{1}{3}$",
                    "aliases": [],
                }
            ],
        }
    )

    assert "explanation_latex: |-\n  一行解析。" in yaml_text
    assert "aliases: []" in yaml_text
