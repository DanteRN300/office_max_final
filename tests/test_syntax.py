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
def test_streamlit_app_and_model_modules_compile():
    """Regression check for syntax/indentation errors in Streamlit deploy files."""
    repo_root = Path(__file__).resolve().parents[1]
    for relative_path in [
        "app.py",
        "modules/elasticity.py",
        "modules/historical_ml.py",
    ]:
        py_compile.compile(str(repo_root / relative_path), doraise=True)
def test_streamlit_app_and_elasticity_module_compile():
    """Regression check for syntax/indentation errors in Streamlit deploy files."""
    repo_root = Path(__file__).resolve().parents[1]
    py_compile.compile(str(repo_root / "app.py"), doraise=True)
    py_compile.compile(str(repo_root / "modules" / "elasticity.py"), doraise=True)
