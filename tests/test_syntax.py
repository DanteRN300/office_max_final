import py_compile
from pathlib import Path


def test_streamlit_app_and_elasticity_module_compile():
    """Regression check for syntax/indentation errors in Streamlit deploy files."""
    repo_root = Path(__file__).resolve().parents[1]
    py_compile.compile(str(repo_root / "app.py"), doraise=True)
    py_compile.compile(str(repo_root / "modules" / "elasticity.py"), doraise=True)
