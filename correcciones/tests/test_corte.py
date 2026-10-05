import json
from fractions import Fraction
from pathlib import Path

import pytest

from corte import discover_test_names, final_grade, load_config, run_tests, score

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_FILES = sorted((ROOT / "correcciones").glob("corte-*/corte.json"))
TEMPLATE_QUESTIONS = ROOT / "repo-template" / "corte-preguntas-1" / "preguntas.json"
READINGS = ["tuesday-week-1", "thursday-week-1", "tuesday-week-2", "thursday-week-2"]


def grade_file(config, path, work_dir):
    return score(config, run_tests(config.test_file, path, work_dir))


def question(reading, kind, number, level):
    options = ["Verdadero", "Falso"] if kind == "true_false" else ["Opción A", "Opción B", "Opción C"]
    return {"id": f"{reading}-{kind}-{number}", "reading": reading, "type": kind,
            "statement": f"Pregunta {number} {kind} de {reading}", "options": options,
            "correct_option": options[0], "difficulty_level": level}


def full_submission(levels=(1, 2, 4, 5, 6, 3, 5, 6, 8, 9)):
    """40 valid questions; per reading 5 true/false + 5 multiple choice with the given difficulty levels."""
    questions = []
    for reading in READINGS:
        for number, level in enumerate(levels):
            questions.append(question(reading, "true_false" if number < 5 else "multiple_choice", number, level))
    return questions


def write_questions(tmp_path, questions):
    path = tmp_path / "preguntas.json"
    path.write_text(json.dumps({"team": "t", "questions": questions}), encoding="utf-8")
    return path


# --- Gates discovered from disk: every correcciones/corte-*/corte.json is subject ---

def test_gate_discovers_at_least_one_corte():
    assert CONFIG_FILES, "No correcciones/corte-*/corte.json found: the gate would pass without proving anything"


@pytest.mark.parametrize("config_file", CONFIG_FILES, ids=lambda path: path.parent.name)
def test_gate_every_test_of_the_template_belongs_to_exactly_one_criterion(config_file):
    config = load_config(config_file)
    discovered = discover_test_names(config.test_file)
    mapped = {name for criterion in config.criteria for name in criterion.tests}
    assert discovered, f"No tests found in {config.test_file}"
    assert discovered - mapped == set(), f"Tests that count for nothing (add them to {config_file.name}): {sorted(discovered - mapped)}"
    assert mapped - discovered == set(), f"Stale tests in {config_file.name}: {sorted(mapped - discovered)}"


@pytest.mark.parametrize("config_file", CONFIG_FILES, ids=lambda path: path.parent.name)
def test_gate_the_untouched_template_scores_the_minimum_grade(config_file, tmp_path):
    config = load_config(config_file)
    result = grade_file(config, TEMPLATE_QUESTIONS, tmp_path)
    assert result.tests_passed == 0, f"The untouched template passes tests, it earns points for nothing: {result.failures()[:3]}"
    assert final_grade(config, result.points) == config.minimum_grade


# --- Scoring against synthetic submissions ---

def test_a_complete_submission_gets_the_maximum_grade(tmp_path):
    config = load_config(CONFIG_FILES[0])
    result = grade_file(config, write_questions(tmp_path, full_submission()), tmp_path / "work")
    assert result.failures() == []
    assert final_grade(config, result.points) == config.maximum_grade


def test_an_empty_questions_list_scores_the_minimum_not_a_vacuous_pass(tmp_path):
    config = load_config(CONFIG_FILES[0])
    result = grade_file(config, write_questions(tmp_path, []), tmp_path / "work")
    assert result.tests_passed == 0 and final_grade(config, result.points) == config.minimum_grade


def test_a_missing_file_scores_the_minimum(tmp_path):
    config = load_config(CONFIG_FILES[0])
    result = grade_file(config, tmp_path / "does-not-exist.json", tmp_path / "work")
    assert final_grade(config, result.points) == config.minimum_grade


def test_without_hard_questions_only_that_criterion_is_lost(tmp_path):
    config = load_config(CONFIG_FILES[0])
    result = grade_file(config, write_questions(tmp_path, full_submission(levels=(1, 2, 4, 5, 6, 3, 5, 6, 7, 7))), tmp_path / "work")
    points = {s.key: s.points for s in result.scores}
    assert points["hard"] == 0 and points["easy"] == 5 and points["format"] == 5 and points["count"] == 5
    assert final_grade(config, result.points) == 15


def test_level_boundaries_are_strict(tmp_path):
    config = load_config(CONFIG_FILES[0])
    # level 3 is NOT easy (< 3) and level 7 is NOT hard (> 7)
    result = grade_file(config, write_questions(tmp_path, full_submission(levels=(3, 3, 4, 5, 6, 3, 5, 6, 7, 7))), tmp_path / "work")
    points = {s.key: s.points for s in result.scores}
    assert points["easy"] == 0 and points["hard"] == 0


def test_a_missing_question_costs_part_of_the_count_criterion(tmp_path):
    config = load_config(CONFIG_FILES[0])
    questions = full_submission()[:-1]
    result = grade_file(config, write_questions(tmp_path, questions), tmp_path / "work")
    count = next(s for s in result.scores if s.key == "count")
    assert 0 < count.points < 5
    assert any("exactly_40" in name for name, _ in result.failures())


def test_one_placeholder_left_is_a_missing_question_not_a_valid_one(tmp_path):
    config = load_config(CONFIG_FILES[0])
    questions = full_submission()
    questions[0]["statement"] = "PONGAN AQUÍ SU PREGUNTA VERDADERO/FALSO #1"
    result = grade_file(config, write_questions(tmp_path, questions), tmp_path / "work")
    failed = {name for name, _ in result.failures()}
    assert "test_no_template_placeholders_left" in failed and "test_there_are_exactly_40_questions" in failed


# --- Grade math ---

def test_rounding_is_half_up_and_penalty_cannot_go_below_the_minimum():
    config = load_config(CONFIG_FILES[0])
    assert final_grade(config, Fraction(25, 2)) == 13          # 12.5 -> 13, not banker's 12
    assert final_grade(config, Fraction(20), penalty=2) == 18
    assert final_grade(config, Fraction(2), penalty=10) == config.minimum_grade
    with pytest.raises(ValueError):
        final_grade(config, Fraction(20), penalty=20)


def test_config_rejects_points_that_do_not_add_up(tmp_path):
    raw = json.loads(CONFIG_FILES[0].read_text(encoding="utf-8"))
    raw["criteria"][0]["points"] = 6
    broken = tmp_path / "corte.json"
    broken.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(broken)
