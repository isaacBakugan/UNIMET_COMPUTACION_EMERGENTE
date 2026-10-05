"""Grade a `corte-preguntas-N` deliverable by running the SAME pytest file students run.

The authoritative tests live in `repo-template/` (what students receive). The grader runs that file
from the central repo against the team's `preguntas.json` at the cutoff commit (env QUESTIONS_FILE),
never the copy inside the student repo, which they could edit. Each criterion of `corte.json`
groups test functions; its points are proportional to the test instances that pass.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from fractions import Fraction
from math import floor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Criterion:
    key: str
    description: str
    points: int
    tests: tuple[str, ...]


@dataclass(frozen=True)
class CorteConfig:
    name: str
    cutoff: str
    folder: str
    deliverable: str
    test_file: Path
    minimum_grade: int
    maximum_grade: int
    late_penalty_points: int
    excluded_teams: tuple[str, ...]
    criteria: tuple[Criterion, ...]


@dataclass
class CriterionScore:
    key: str
    passed: int
    total: int
    points: Fraction


@dataclass
class TestOutcome:
    __test__ = False  # not a pytest test class, despite the name

    passed: bool
    message: str = ""


@dataclass
class CorteResult:
    outcomes: dict[str, list[TestOutcome]] = field(default_factory=dict)   # base test name -> instances
    scores: list[CriterionScore] = field(default_factory=list)

    @property
    def points(self) -> Fraction:
        return sum((score.points for score in self.scores), Fraction(0))

    @property
    def tests_passed(self) -> int:
        return sum(score.passed for score in self.scores)

    @property
    def tests_total(self) -> int:
        return sum(score.total for score in self.scores)

    def failures(self) -> list[tuple[str, str]]:
        return [(name, outcome.message) for name, instances in self.outcomes.items()
                for outcome in instances if not outcome.passed]


def load_config(path: Path) -> CorteConfig:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    criteria = tuple(Criterion(item["key"], item["description"], item["points"], tuple(item["tests"]))
                     for item in raw["criteria"])
    if sum(c.points for c in criteria) != raw["maximum_grade"]:
        raise ValueError(f"Criteria points must add up to maximum_grade ({raw['maximum_grade']})")
    mapped = [name for c in criteria for name in c.tests]
    if len(set(mapped)) != len(mapped) or not all(c.tests for c in criteria):
        raise ValueError("Every criterion needs tests, and a test can belong to only one criterion")
    if not 0 <= raw["minimum_grade"] < raw["maximum_grade"]:
        raise ValueError("minimum_grade must be >= 0 and lower than maximum_grade")
    if not 0 <= raw["late_penalty_points"] < raw["maximum_grade"]:
        raise ValueError("late_penalty_points must be >= 0 and lower than maximum_grade")
    return CorteConfig(raw["name"], raw["cutoff"], raw["folder"], raw["deliverable"], ROOT / raw["test_file"],
                       raw["minimum_grade"], raw["maximum_grade"], raw["late_penalty_points"],
                       tuple(raw.get("excluded_teams", [])), criteria)


def discover_test_names(test_file: Path) -> set[str]:
    """Top-level `test_*` functions of the authoritative test file, found by parsing it (no imports)."""
    tree = ast.parse(test_file.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


def run_tests(test_file: Path, questions_file: Path, work_dir: Path, timeout: int = 120) -> dict[str, list[TestOutcome]]:
    """Run the authoritative tests against `questions_file`; return outcomes per base test name."""
    work_dir.mkdir(parents=True, exist_ok=True)
    report = work_dir / "pytest.xml"
    report.unlink(missing_ok=True)
    command = [sys.executable, "-m", "pytest", str(test_file), "-q", "--tb=short", "-p", "no:cacheprovider",
               f"--junitxml={report}"]
    run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, env={**os.environ, "QUESTIONS_FILE": str(questions_file)}, cwd=ROOT)
    (work_dir / "pytest.txt").write_text(run.stdout + run.stderr, encoding="utf-8")
    if not report.exists():
        raise RuntimeError(f"pytest produced no report (exit {run.returncode}): {run.stderr.strip()[:300]}")
    outcomes: dict[str, list[TestOutcome]] = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        problem = next((node for tag in ("failure", "error", "skipped") if (node := case.find(tag)) is not None), None)
        message = ""
        if problem is not None:
            first_line = (problem.get("message") or "").splitlines()
            message = (first_line[0] if first_line else "").removeprefix("AssertionError: ").strip()
        base = case.get("name", "").split("[")[0]
        outcomes.setdefault(base, []).append(TestOutcome(problem is None, message))
    return outcomes


def score(config: CorteConfig, outcomes: dict[str, list[TestOutcome]]) -> CorteResult:
    """Points per criterion = criterion points x passed / total test instances (exact fractions)."""
    result = CorteResult(outcomes=outcomes)
    for criterion in config.criteria:
        instances = [outcome for name in criterion.tests for outcome in outcomes.get(name, [])]
        passed = sum(outcome.passed for outcome in instances)
        points = Fraction(criterion.points * passed, len(instances)) if instances else Fraction(0)
        result.scores.append(CriterionScore(criterion.key, passed, len(instances), points))
    return result


def final_grade(config: CorteConfig, points: Fraction, penalty: int = 0) -> int:
    """Half-up rounding (not banker's), minus the accepted-late penalty, never below the minimum."""
    if not 0 <= penalty < config.maximum_grade:
        raise ValueError(f"Invalid penalty: {penalty}")
    return max(config.minimum_grade, floor(points + Fraction(1, 2)) - penalty)
