"""Tarea 2 network metadata, console profiles and evidence scoring; no student execution."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from rubrica import CaseResult

CASE_KEYS = ("given_network_2d_2class", "given_network_3d_4class",
             "hidden_training_2d_2class", "hidden_training_3d_4class")
FILES = tuple(f"perceptron_multicapa_{n}.py" for n in range(1, 4))
FOLDER = "tarea-2-codigo"


def network_metadata(path: Path) -> dict[str, int]:
    """Read the five hyperparameters without interpreting activation or rewriting weights."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    if len(rows) < 7:
        raise ValueError(f"{path.name}: missing header, hyperparameters or neurons")
    metadata = {}
    # Some existing submissions put the header after the five parameters. Read their own
    # metadata without repairing the network CSV; the student loader still receives the original.
    parameter_rows = rows[:5] if rows[0][0].strip() == "u" else rows[1:6]
    for row, key in zip(parameter_rows, ("u", "v", "L", "b", "e")):
        if len(row) < 2 or row[0].strip() != key or any(cell.strip() for cell in row[2:]):
            raise ValueError(f"{path.name}: invalid hyperparameter row {key}")
        value = float(row[1])
        if not math.isfinite(value) or not value.is_integer() or value < (0 if key in ("L", "e") else 1):
            raise ValueError(f"{path.name}: invalid value for {key}")
        metadata[key] = int(value)
    return metadata


def load_profiles(path: Path) -> list[dict]:
    items = json.loads(path.read_text(encoding="utf-8-sig"))
    seen = set()
    for item in items:
        key = (item["team"], item["file"], item["commit"])
        if key in seen or not item.get("reason", "").strip():
            raise ValueError(f"Invalid or duplicated console profile: {key}")
        seen.add(key)
        for case, spec in item["cases"].items():
            if case not in CASE_KEYS or set(spec) - {"network", "answers"}:
                raise ValueError(f"Invalid profile case: {key}/{case}")
            if "answers" in spec and (not isinstance(spec["answers"], list) or
                                      not all(isinstance(x, str) for x in spec["answers"])):
                raise ValueError(f"Invalid answer list: {key}/{case}")
    return items


def select_network(source_dir: Path, filename: str, dimensions: int, classes: int,
                   explicit: str | None = None) -> tuple[Path, dict]:
    """Use the individual conventional filename or a commit-pinned explicit path; never guess ownership."""
    number = filename.removesuffix(".py").rsplit("_", 1)[1]
    relative = explicit or f"red_{dimensions}d_{classes}clases_{number}.csv"
    path = (source_dir / relative).resolve()
    if not path.is_relative_to(source_dir.resolve()) or not path.is_file():
        raise ValueError(f"Missing individual network: {relative}")
    metadata = network_metadata(path)
    if (metadata["u"], metadata["v"]) != (dimensions, classes):
        raise ValueError(f"{path.name}: expected u={dimensions}, v={classes}; got {metadata}")
    return path, metadata


def console_answers(case: str, metadata: dict, network: str) -> list[str]:
    dimensions, classes = metadata["u"], metadata["v"]
    if case.startswith("given"):
        return ["2", network, "2", f"/data/{dimensions}-d_{classes}-class_test.csv", "4"]
    prefix = f"hidden_{dimensions}d_{classes}class"
    return ["1", str(dimensions), str(classes), str(metadata["L"]), str(metadata["b"]),
            "1", f"/data/{prefix}_train.csv", str(metadata["e"]),
            "2", f"/data/{prefix}_test.csv", "4"]


def score_trace(trace: dict, expected_counts: list[int], status: str) -> CaseResult:
    """Require a full confusion matrix with the independently known class supports, no accuracy threshold."""
    if status != "ok" or trace.get("error"):
        return CaseResult("no_result", f"Ejecución incompleta ({status}). {trace.get('error', '')[-600:]}", True)
    # Only test-stage matrices count; training output cannot substitute for the requested test.
    matrices = trace.get("test_matrices", [])
    size, total = len(expected_counts), sum(expected_counts)
    for matrix in reversed(matrices):
        if len(matrix) != size or any(len(row) != size for row in matrix):
            continue
        if any(not math.isfinite(x) or x < 0 or x != int(x) for row in matrix for x in row):
            continue
        row_counts = [sum(row) for row in matrix]
        col_counts = [sum(row[i] for row in matrix) for i in range(size)]
        # Both common orientations are accepted, but incomplete/normalized matrices are not.
        if row_counts != expected_counts and col_counts != expected_counts:
            continue
        correct = sum(matrix[i][i] for i in range(size))
        outcome = "correct" if correct == total else "incorrect"
        return CaseResult(outcome, f"Matriz de confusión de prueba: {int(correct)}/{total} clasificaciones correctas. "
                          "Verificar las gráficas y la correspondencia de las etiquetas.", True)
    return CaseResult("no_result", "No hay matriz de confusión de prueba verificable con cobertura de todas las filas. "
                      "Revisar la traza, el menú y las gráficas; la falta de captura no demuestra que la red falle.", True)
