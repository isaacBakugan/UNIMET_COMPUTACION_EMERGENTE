"""Grading rubric for Tarea 1 (perceptron): scale loading, grade math and case scoring.

Pure logic, no I/O besides reading the rubric JSON, so it can be unit tested without
git, WSL or student code. The functional criteria are visual judgments in the original
rubric ("separates correctly"); here they are proxied by the counts of the third plot
(green = predicted matches expected, red = mismatch). Cases where the proxy is weak are
flagged `needs_review` so the professor knows where to look at the PNG.
"""

from __future__ import annotations

import colorsys
import json
from dataclasses import dataclass, field
from pathlib import Path

CASE_KEYS = ("given_separable", "given_non_separable", "hidden_separable", "hidden_non_separable")
OUTCOMES = ("correct", "incorrect", "no_result")


@dataclass(frozen=True)
class Rubric:
    name: str
    cutoff: str
    minimum_grade: int
    maximum_grade: int
    late_penalty_points: int
    excluded_teams: tuple[str, ...]
    criteria: dict[str, dict]

    def points(self, case: str, outcome: str) -> int:
        return self.criteria[case][outcome]

    def description(self, case: str) -> str:
        return self.criteria[case]["description"]

    @property
    def max_points(self) -> int:
        return sum(item["correct"] for item in self.criteria.values())


def load_rubric(path: Path) -> Rubric:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    items = config["criteria"]
    keys = [item["key"] for item in items]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError(f"The rubric needs at least one criterion and unique keys: {keys}")
    for item in items:
        scores = [item[outcome] for outcome in OUTCOMES]
        if not all(type(score) is int for score in scores) or not scores[0] > scores[1] > scores[2] >= 0:
            raise ValueError(f"Invalid scale in criterion {item['key']}: need correct > incorrect > no_result >= 0")
        if not item.get("description"):
            raise ValueError(f"Missing description in criterion {item['key']}")
    if not 0 <= config["minimum_grade"] < config["maximum_grade"]:
        raise ValueError("minimum_grade must be >= 0 and lower than maximum_grade")
    if not 0 <= config["late_penalty_points"] < config["maximum_grade"]:
        raise ValueError("late_penalty_points must be >= 0 and lower than maximum_grade")
    return Rubric(
        name=config["name"], cutoff=config["cutoff"],
        minimum_grade=config["minimum_grade"], maximum_grade=config["maximum_grade"],
        late_penalty_points=config["late_penalty_points"],
        excluded_teams=tuple(config.get("excluded_teams", [])),
        criteria={item["key"]: item for item in items})


def rubric_grade(rubric: Rubric, outcomes: dict[str, str]) -> tuple[int, int]:
    """Return (rubric points, grade on the final scale before any late penalty)."""
    total = sum(rubric.points(case, outcomes[case]) for case in rubric.criteria)
    grade = round(total * rubric.maximum_grade / rubric.max_points)
    return total, max(rubric.minimum_grade, grade)


def final_grade(rubric: Rubric, rubric_grade_value: int, penalty: int) -> int:
    if not 0 <= penalty < rubric.maximum_grade:
        raise ValueError(f"Invalid penalty: {penalty}")
    return max(rubric.minimum_grade, rubric_grade_value - penalty)


def color_category(hex_color: str) -> str:
    """Classify a `#rrggbb` color as green / red / other by hue, tolerant to shades."""
    rgb = tuple(int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, saturation, value = colorsys.rgb_to_hsv(*rgb)
    if saturation >= 0.3 and value >= 0.2:
        if 0.24 <= hue <= 0.47:
            return "green"
        if hue <= 0.055 or hue >= 0.96:
            return "red"
    return "other"


@dataclass
class CaseEvidence:
    """What the sandbox observed for one (file, case) run."""
    status: str = "missing"          # ok | error_<code> | timeout | missing
    plots: int = 0
    expected_points: int = 0         # points in the 1st axis of the main figure
    predicted_points: int = 0        # points in the 2nd axis
    compared_points: int = 0         # points in the 3rd axis (comparison)
    green: int = 0
    red: int = 0
    figure: str = ""                 # PNG of the main figure, relative to the evidence dir
    failure: str = ""                # last traceback line, if any
    extra: dict = field(default_factory=dict)


@dataclass
class CaseResult:
    outcome: str
    explanation: str
    needs_review: bool = False
    source: str = "automatic"        # automatic | teacher_decision | no_submission


def score_case(case: str, evidence: CaseEvidence) -> CaseResult:
    """Map the sandbox evidence of one case to a rubric outcome plus a Spanish explanation."""
    if evidence.status == "missing":
        return CaseResult("no_result", "Falta la ejecución o la captura; revisar el entorno antes de cerrar la nota.", True)
    if evidence.status != "ok":
        if evidence.plots:
            return CaseResult("incorrect", f"La ejecución terminó con estado {evidence.status} después de producir una gráfica parcial.", True)
        detail = f" Último error: {evidence.failure}" if evidence.failure else ""
        return CaseResult("no_result", f"El programa no produjo gráfica para este caso (estado {evidence.status}).{detail}", True)

    total, green, red = evidence.compared_points, evidence.green, evidence.red
    if total == 0:
        return CaseResult("incorrect", "El programa terminó, pero falta la tercera gráfica de comparación.", True)

    if case == "given_separable":
        # The public CSV has fuzzy labels (decimals besides 0/1): exact equality is not required.
        if evidence.expected_points < total or evidence.predicted_points < total:
            return CaseResult("incorrect", (
                f"Gráfica incompleta: esperado {evidence.expected_points}, predicho "
                f"{evidence.predicted_points}, comparación {total} puntos. Revisar visualmente."), True)
        if green > red:
            return CaseResult("correct", (
                f"{green}/{total} coincidencias y dos regiones visibles. El CSV público tiene "
                "etiquetas difusas; confirmar visualmente la separación."), True)
        return CaseResult("incorrect", (
            f"Solo {green}/{total} coincidencias en el ejemplo dado; confirmar si la clasificación separa las clases."), True)

    if case == "hidden_separable":
        if green == total and red == 0:
            return CaseResult("correct", f"{green}/{total} coincidencias en el caso separable nuevo.")
        return CaseResult("incorrect", f"{green}/{total} coincidencias y {red} errores en el caso separable nuevo.", True)

    # given_non_separable / hidden_non_separable: a perfect fit would mean the data got separated.
    if red > 0 and green > 0:
        return CaseResult("correct", (
            f"La gráfica muestra {red} errores y {green} coincidencias de {total}; "
            "no separa por completo este conjunto."))
    return CaseResult("incorrect", (
        f"La tercera gráfica tiene {green} coincidencias y {red} errores de {total}; "
        "revisar si representa correctamente un conjunto no separable."), True)
