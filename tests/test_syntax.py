import py_compile
from pathlib import Path


def test_streamlit_app_and_model_modules_compile():
    """Regression check for syntax/indentation errors in Streamlit deploy files."""
    repo_root = Path(__file__).resolve().parents[1]
    for relative_path in [
        "app.py",
        "modules/elasticity.py",
        "modules/historical_ml.py",
    ]:
        py_compile.compile(str(repo_root / relative_path), doraise=True)
