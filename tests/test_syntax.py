import py_compile
from pathlib import Path


def test_all_python_files_compile():
    """Regression check for syntax/indentation errors in every deploy Python file."""
    repo_root = Path(__file__).resolve().parents[1]
    python_files = [
        path
        for path in repo_root.rglob("*.py")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    ]
    assert python_files, "No Python files found to compile."
    for path in python_files:
        py_compile.compile(str(path), doraise=True)
