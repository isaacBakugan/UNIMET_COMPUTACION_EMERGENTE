import csv
import json
import os
import subprocess
from pathlib import Path

import pytest

from calificador import load_overrides
from entregas import commit_at_cutoff, static_review, student_identity, to_utc_iso
from rubrica import (CASE_KEYS, CaseEvidence, final_grade, color_category, load_rubric, rubric_grade, score_case)
from sandbox import CASE_INPUTS, CASES_DIR

CORRECTIONS_DIR = Path(__file__).resolve().parent.parent
ASSIGNMENT_DIRS = sorted(path.parent for path in CORRECTIONS_DIR.glob("tarea-*/tarea.json"))


def write_rubric(tmp_path, **changes):
    config = json.loads((CORRECTIONS_DIR / "tarea-1" / "tarea.json").read_text(encoding="utf-8"))
    config.update(changes)
    path = tmp_path / "tarea.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def evidence(**changes):
    return CaseEvidence(**{"status": "ok", "plots": 1, "expected_points": 10, "predicted_points": 10,
                           "compared_points": 10, "green": 10, "red": 0, **changes})


# --- Gates discovered from disk: any tarea-*/ folder is subject, nothing is imported by name ---

def test_gate_discovers_at_least_one_assignment():
    assert ASSIGNMENT_DIRS, "No correcciones/tarea-*/tarea.json found: the gate would pass without proving anything"


@pytest.mark.parametrize("assignment_dir", ASSIGNMENT_DIRS, ids=lambda path: path.name)
def test_gate_every_assignment_config_is_loadable_and_complete(assignment_dir):
    rubric = load_rubric(assignment_dir / "tarea.json")
    to_utc_iso(rubric.cutoff)
    overrides = load_overrides(assignment_dir / "decisiones-docente.json")
    for item in overrides:
        assert item["team"] not in rubric.excluded_teams, f"Teacher decision for an excluded team: {item['team']}"
    for name, columns in (("alumnos.csv", {"team", "file", "student_name", "national_id"}),
                          ("entregas-tardias.csv", {"team", "file", "commit", "penalty_points", "reason"})):
        with (assignment_dir / name).open(newline="", encoding="utf-8-sig") as file:
            assert set(csv.DictReader(file).fieldnames) == columns, f"Unexpected columns in {assignment_dir.name}/{name}"


def test_gate_every_sandbox_case_has_its_dataset():
    assert set(CASE_INPUTS) == set(CASE_KEYS)
    for case, (csv_path, _) in CASE_INPUTS.items():
        if csv_path.startswith("/data/"):
            dataset = CASES_DIR / csv_path.removeprefix("/data/")
            assert dataset.exists(), f"Missing hidden dataset for {case}: {dataset}"
            header = dataset.read_text(encoding="utf-8").splitlines()[0].strip()
            assert header == "x1,x2,y", f"Unexpected header in {dataset.name}: {header}"


# --- Rubric math ---

def test_perfect_submission_is_the_maximum_grade():
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json")
    assert rubric_grade(rubric, dict.fromkeys(CASE_KEYS, "correct")) == (100, 20)


def test_empty_submission_gets_the_minimum_grade_not_zero():
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json")
    points, grade = rubric_grade(rubric, dict.fromkeys(CASE_KEYS, "no_result"))
    assert (points, grade) == (0, rubric.minimum_grade)


def test_late_penalty_never_goes_below_the_minimum_and_rejects_nonsense():
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json")
    assert final_grade(rubric, 20, 2) == 18
    assert final_grade(rubric, 3, 10) == rubric.minimum_grade
    with pytest.raises(ValueError):
        final_grade(rubric, 20, 20)


def test_rubric_rejects_an_inverted_scale(tmp_path):
    config = json.loads((CORRECTIONS_DIR / "tarea-1" / "tarea.json").read_text(encoding="utf-8"))
    config["criteria"][0]["incorrect"] = 30
    with pytest.raises(ValueError):
        load_rubric(write_rubric(tmp_path, criteria=config["criteria"]))


# --- Case scoring ---

def test_color_category_tolerates_shades():
    assert color_category("#008000") == "green" and color_category("#00ff00") == "green"
    assert color_category("#ff0000") == "red" and color_category("#d62728") == "red"
    assert color_category("#1f77b4") == "other"


def test_hidden_separable_requires_a_perfect_comparison():
    assert score_case("hidden_separable", evidence()).outcome == "correct"
    assert score_case("hidden_separable", evidence(green=9, red=1)).outcome == "incorrect"


def test_non_separable_case_needs_both_colors():
    assert score_case("hidden_non_separable", evidence(green=4, red=4)).outcome == "correct"
    assert score_case("hidden_non_separable", evidence(green=10, red=0)).outcome == "incorrect"


def test_given_separable_flags_incomplete_plots_for_review():
    result = score_case("given_separable", evidence(expected_points=8, compared_points=10))
    assert result.outcome == "incorrect" and result.needs_review


def test_a_crash_without_plots_is_no_result_and_a_partial_plot_is_incorrect():
    assert score_case("hidden_separable", evidence(status="error_1", plots=0, compared_points=0)).outcome == "no_result"
    assert score_case("hidden_separable", evidence(status="timeout", plots=1)).outcome == "incorrect"


# --- Static review and identity ---

def test_student_identity_reads_the_header():
    assert student_identity("# Nombre del integrante: Ana Pérez\n# Cédula del integrante: 123\nx = 1") == ("Ana Pérez", "123")
    assert student_identity("# Nombre del integrante: \n# Cédula del integrante: \n") == ("", "")


def test_template_is_detected_as_empty_and_forbidden_imports_are_listed():
    assert static_review("# Nombre del integrante: \n# haga su tarea aqui\n")["empty"]
    review = static_review("import os\nfrom numpy import array\nimport matplotlib.pyplot as plt\n")
    assert review["forbidden_imports"] == ["numpy", "os"] and not review["empty"]
    assert not static_review("def broken(:\n")["syntax_ok"]


# --- Cutoff selection against a real git repository ---

def commit_on(repo, name, date):
    (repo / "f.txt").write_text(name, encoding="utf-8")
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True, env={**os.environ, **env})
    subprocess.run(["git", "-C", str(repo), "commit", "-m", name], check=True, capture_output=True, env={**os.environ, **env})
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def test_commit_at_cutoff_respects_the_timezone(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    before = commit_on(tmp_path, "before", "2026-09-27T23:30:00-04:00")
    commit_on(tmp_path, "after", "2026-09-28T00:30:00-04:00")
    assert commit_at_cutoff(tmp_path, "2026-09-28T00:00:00-04:00") == before
    assert commit_at_cutoff(tmp_path, "2026-09-26T00:00:00-04:00") is None
    with pytest.raises(ValueError):
        commit_at_cutoff(tmp_path, "2026-09-28T00:00:00")
