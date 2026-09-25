import ast
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Assignment requirement: "No se permite el uso de otras librerías excepto matplotlib".
# Interpreted literally: any other import (including the standard library) is a violation.
ALLOWED_LIBRARIES = {"matplotlib"}

def _get_target_file():
    filename = os.environ.get("PERCEPTRON_FILE")
    assert filename, (
        "Debe especificar la variable de entorno PERCEPTRON_FILE.\n"
        "Ejemplo en PowerShell: $env:PERCEPTRON_FILE='perceptron_1.py'; pytest ..."
    )
    return BASE_DIR / filename

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

def test_individual_file_exists():
    file = _get_target_file()
    assert file.exists(), f"El archivo {file.name} no existe en tarea-1-codigo/"

def test_individual_is_valid_python():
    file = _get_target_file()
    code = file.read_text(encoding="utf-8")
    ast.parse(code)

def test_individual_does_not_import_anything_besides_matplotlib():
    file = _get_target_file()
    code = file.read_text(encoding="utf-8")
    modules = _imported_modules(code)
    disallowed = modules - ALLOWED_LIBRARIES
    assert not disallowed, (
        f"Solo se puede importar matplotlib en {file.name}. Importado: {disallowed}"
    )
