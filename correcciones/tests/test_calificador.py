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


def test_gate_tarea_1_rubric_keeps_the_criteria_the_sandbox_runs():
    # load_rubric accepts any criteria (tarea-2 has its own); the Tarea 1 corrector depends on these four.
    assert tuple(load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json").criteria) == CASE_KEYS


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


def test_tarea_3_five_level_scale_grades_from_the_best_and_worst_outcomes():
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-3" / "tarea.json")
    assert set(rubric.criteria) == {"original_rectangular", "original_convolutional",
                                    "simplified_rectangular", "simplified_convolutional"}
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "great_majority")) == (100, 20)
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "no_result")) == (0, rubric.minimum_grade)
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "majority"))[0] == 60


@pytest.mark.parametrize("change", [
    {"majority": 30},                                           # inverted points scale
    {"thresholds": {"great_majority": 0.5, "majority": 0.75}},  # ascending thresholds
    {"thresholds": {"great_majority": 1.0}},                    # unreachable level
    {"thresholds": {"majority": 0.5, "great_majority": 0.75}},  # not in scale order
    {"thresholds": {"unknown_level": 0.5}},                     # outcome outside the scale
], ids=["inverted-points", "ascending", "unreachable", "out-of-order", "unknown-level"])
def test_rubric_rejects_a_broken_five_level_scale(tmp_path, change):
    config = json.loads((CORRECTIONS_DIR / "tarea-3" / "tarea.json").read_text(encoding="utf-8"))
    config["criteria"][0].update(change)
    with pytest.raises(ValueError):
        load_rubric(write_rubric(tmp_path, criteria=config["criteria"]))


def test_tarea_4_weights_each_criterion_by_its_own_scale():
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-4" / "tarea.json")
    assert tuple(rubric.criteria) == ("low_mutation_function_a", "high_mutation_function_a",
                                      "low_mutation_function_b", "high_mutation_function_b")
    assert rubric.max_points == 100
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "adequate")) == (100, 20)
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "no_result")) == (0, rubric.minimum_grade)
    # Function b weighs 30% per population, function a 20%: losing b costs more than losing a.
    only_a_adequate = {key: "adequate" if key.endswith("function_a") else "no_result" for key in rubric.criteria}
    only_b_adequate = {key: "adequate" if key.endswith("function_b") else "no_result" for key in rubric.criteria}
    assert rubric_grade(rubric, only_a_adequate)[0] == 40
    assert rubric_grade(rubric, only_b_adequate)[0] == 60


def test_tarea_5_is_a_group_task_graded_half_and_half():
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-5" / "tarea.json")
    assert tuple(rubric.criteria) == ("blank_grid_add_zone", "loaded_city_updates")
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "correct")) == (100, 20)
    assert rubric_grade(rubric, dict.fromkeys(rubric.criteria, "no_result")) == (0, rubric.minimum_grade)
    assert rubric_grade(rubric, {"blank_grid_add_zone": "correct", "loaded_city_updates": "no_result"})[0] == 50
    # One deliverable per team: the support list has one row per team, not three per team.
    with (CORRECTIONS_DIR / "tarea-5" / "alumnos.csv").open(newline="", encoding="utf-8-sig") as file:
        teams = [row["team"] for row in csv.DictReader(file)]
    assert teams and len(teams) == len(set(teams)), "tarea-5/alumnos.csv must list each team exactly once"


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


# --- Late policy for Tarea 1: the better of (cutoff version, latest version minus the penalty) ---

def make_version(version, outcome, penalty):
    from calificador import Submission
    from rubrica import CaseResult
    submission = Submission("T", "T-repo", "perceptron_1.py", penalty=penalty, version=version)
    submission.cases = {case: CaseResult(outcome, "x") for case in CASE_KEYS}
    if version == "late":
        submission.late_commits = ["2026-10-04T21:20:58-04:00"]
    return submission


def test_late_delivery_is_graded_with_the_penalty_when_nothing_arrived_on_time():
    from calificador import pick_best_versions
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json")
    on_time, late = make_version("cutoff", "no_result", 0), make_version("late", "correct", rubric.late_penalty_points)
    warnings = []
    assert pick_best_versions([on_time, late], rubric, warnings) == [late]
    assert warnings and "descuento de 2" in warnings[0]


def test_a_late_commit_does_not_replace_an_equal_or_better_on_time_version():
    from calificador import pick_best_versions
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json")
    on_time, late = make_version("cutoff", "correct", 0), make_version("late", "correct", rubric.late_penalty_points)
    assert pick_best_versions([on_time, late], rubric, []) == [on_time]


def test_a_crashing_late_version_does_not_beat_the_minimum_grade_of_the_cutoff_version():
    from calificador import pick_best_versions
    rubric = load_rubric(CORRECTIONS_DIR / "tarea-1" / "tarea.json")
    on_time, late = make_version("cutoff", "no_result", 0), make_version("late", "no_result", rubric.late_penalty_points)
    assert pick_best_versions([on_time, late], rubric, []) == [on_time]
