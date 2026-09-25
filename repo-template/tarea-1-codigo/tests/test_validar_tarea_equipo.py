import ast
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

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

def test_equipo_files_exist():
    for i in range(1, 4):
        file = BASE_DIR / f"perceptron_{i}.py"
        assert file.exists(), (
            f"Falta {file.name} en tarea-1-codigo/"
        )

def test_equipo_is_valid_python():
    for i in range(1, 4):
        file = BASE_DIR / f"perceptron_{i}.py"
        code = file.read_text(encoding="utf-8")
        ast.parse(code)

def test_equipo_does_not_import_anything_besides_matplotlib():
    for i in range(1, 4):
        file = BASE_DIR / f"perceptron_{i}.py"
        code = file.read_text(encoding="utf-8")
        modules = _imported_modules(code)
        disallowed = modules - ALLOWED_LIBRARIES
        assert not disallowed, (
            f"Solo se puede importar matplotlib en {file.name}. Importado: {disallowed}"
        )
