import ast
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PERCEPTRON_FILE = BASE_DIR / "perceptron.py"

# Assignment requirement: "No se permite el uso de otras librerías excepto matplotlib".
# Interpreted literally: any other import (including the standard library) is a violation.
ALLOWED_LIBRARIES = {"matplotlib"}


def _imported_modules(code):
    tree = ast.parse(code)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


def test_perceptron_py_exists():
    assert PERCEPTRON_FILE.exists(), (
        "Missing perceptron.py in tarea-1-codigo/ (that's the file that gets graded)"
    )


def test_is_valid_python():
    code = PERCEPTRON_FILE.read_text(encoding="utf-8")
    ast.parse(code)


def test_does_not_import_anything_besides_matplotlib():
    code = PERCEPTRON_FILE.read_text(encoding="utf-8")
    modules = _imported_modules(code)
    disallowed = modules - ALLOWED_LIBRARIES
    assert not disallowed, (
        f"Only matplotlib may be imported. Disallowed libraries: {disallowed}"
    )
