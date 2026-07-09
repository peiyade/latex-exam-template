import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def record(question_id="q1", **overrides):
    from quality_core import QuestionRecord

    base = {
        "id": question_id,
        "source_path": Path(f"{question_id}.yaml"),
        "source_metadata": {"file": "source.tex"},
        "schema_version": 1,
        "status": "draft",
        "type": "solution",
        "stem_latex": "Compute $1+1$.",
        "solution_latex": "$2$",
    }
    base.update(overrides)
    return QuestionRecord(**base)


def test_build_render_document_contains_fields_and_preamble():
    from quality_render import build_render_document

    doc = build_render_document(
        record(
            type="choice",
            choices=[{"key": "opt1", "text_latex": "$1$", "correct": True}],
            explanation_latex="Explanation $x$.",
        )
    )

    assert r"\usepackage[fontset=fandol]{ctex}" in doc
    assert r"\begin{document}" in doc
    assert "Compute $1+1$." in doc
    assert "$1$" in doc
    assert "Explanation $x$." in doc


def test_build_render_document_compiles_clean_record_when_xelatex_exists(tmp_path):
    import pytest
    from quality_render import build_render_document

    xelatex = shutil.which("xelatex")
    if not xelatex:
        pytest.skip("xelatex not available")

    tex_path = tmp_path / "q1.tex"
    tex_path.write_text(build_render_document(record("q1")), encoding="utf-8")

    result = subprocess.run(
        [
            xelatex,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory",
            str(tmp_path),
            str(tex_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (result.stdout + result.stderr)[-1000:]


def test_render_cache_key_changes_when_content_changes():
    from quality_render import build_render_document, render_cache_key

    left = build_render_document(record(stem_latex="Compute $1+1$."))
    right = build_render_document(record(stem_latex="Compute $1+2$."))

    assert render_cache_key(record(), left) != render_cache_key(record(), right)


def test_select_records_for_render_modes():
    from quality_core import QualityIssue
    from quality_render import select_records_for_render

    records = [record("q1"), record("q2"), record("q3")]
    issues = [QualityIssue(id="review.clean_required", severity="high", question_id="q2")]

    assert select_records_for_render(records, issues, "off", 2) == []
    assert [item.id for item in select_records_for_render(records, issues, "sample", 1)] == ["q1", "q2"]
    assert [item.id for item in select_records_for_render(records, issues, "full", 1)] == ["q1", "q2", "q3"]


def test_run_render_checks_reports_missing_xelatex(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    issues = run_render_checks(
        [record("q1")],
        [],
        RenderOptions(mode="full", output_dir=tmp_path),
        which=lambda name: None,
    )

    assert issues[0].id == "render.missing_xelatex"
    assert issues[0].severity == "critical"


def test_run_render_checks_reports_failed_compile_with_artifacts(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    def fake_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="! Undefined control sequence.", stderr="")

    issues = run_render_checks(
        [record("q1", stem_latex=r"Bad \unknownmacro")],
        [],
        RenderOptions(mode="full", output_dir=tmp_path, keep_workdir=True),
        runner=fake_runner,
        which=lambda name: "/usr/bin/xelatex",
    )

    assert issues[0].id == "render.compile_failed"
    assert issues[0].severity == "critical"
    assert "Undefined control sequence" in issues[0].message
    assert issues[0].render_artifacts["tex"].exists()


def test_run_render_checks_records_cache_metadata_for_keep_workdir(tmp_path):
    from quality_render import RenderOptions, build_render_document, render_cache_key, run_render_checks

    def fake_runner(args, **kwargs):
        tex_path = Path(args[-1])
        tex_path.with_suffix(".log").write_text("xelatex output", encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    options = RenderOptions(mode="full", output_dir=tmp_path, keep_workdir=True)
    issues = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")

    assert issues == []

    document = build_render_document(record("q1"))
    cache_key = render_cache_key(record("q1"), document)
    cache = json.loads((options.cache_dir / f"{cache_key}.json").read_text(encoding="utf-8"))

    assert cache["success"] is True
    assert "timestamp" in cache
    assert cache["tex_path"].endswith("q1.tex")
    assert cache["log_path"].endswith("q1.log")


def test_run_render_checks_surfaces_warning_only_runs(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    def fake_runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="LaTeX Warning: Label(s) may have changed.\n",
            stderr="Package foo Warning: Something is off.\n",
        )

    issues = run_render_checks(
        [record("q1")],
        [],
        RenderOptions(mode="full", output_dir=tmp_path),
        runner=fake_runner,
        which=lambda name: "/usr/bin/xelatex",
    )

    assert len(issues) == 1
    assert issues[0].id == "render.warning"
    assert issues[0].severity == "medium"
    assert "Warning:" in issues[0].message


def test_run_render_checks_uses_cache_after_success(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    calls = {"count": 0}

    def fake_runner(*args, **kwargs):
        calls["count"] += 1
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    options = RenderOptions(mode="full", output_dir=tmp_path)
    first = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")
    second = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")

    assert first == []
    assert second == []
    assert calls["count"] == 1


def test_run_render_checks_uses_cache_after_failed_compile(tmp_path):
    from quality_render import RenderOptions, run_render_checks

    calls = {"count": 0}

    def fake_runner(*args, **kwargs):
        calls["count"] += 1
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="! Undefined control sequence.", stderr="")

    options = RenderOptions(mode="full", output_dir=tmp_path, keep_workdir=True)
    first = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")
    second = run_render_checks([record("q1")], [], options, runner=fake_runner, which=lambda name: "/usr/bin/xelatex")

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == "render.compile_failed"
    assert second[0].id == "render.compile_failed"
    assert "Undefined control sequence" in second[0].message
    assert calls["count"] == 1
