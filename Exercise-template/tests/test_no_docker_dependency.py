from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_latex_tools_do_not_reference_docker_runtime():
    tool_files = [
        PROJECT_ROOT / "tools" / "compiler.py",
        PROJECT_ROOT / "tools" / "pdf_generator.py",
        PROJECT_ROOT / "tools" / "image_generator.py",
    ]

    forbidden = ["docker", "texlive-bridge", "--container", "container"]

    for path in tool_files:
        text = path.read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle not in text, f"{path.relative_to(PROJECT_ROOT)} still references {needle!r}"
