"""Scoring of corte-preguntas-2 against synthetic submissions: each rule must cost points where it should.

The generic gates (every test belongs to a criterion, the untouched template scores the minimum) live in
test_corte.py and discover every correcciones/corte-*/corte.json by disk.
"""
import json
import random
from pathlib import Path

import pytest

from corte import final_grade, load_config, run_tests, score

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = ROOT / "correcciones" / "corte-preguntas-2" / "corte.json"
READINGS = ["tuesday-week-3", "thursday-week-3", "tuesday-week-4", "thursday-week-4", "tuesday-week-5"]
VOCABULARY = ("perceptron gradiente neurona sesgo umbral capa peso activacion sigmoide frontera lineal entrenamiento "
              "epoca dataset vector matriz derivada error funcion salida entrada propagacion retropropagacion tasa "
              "aprendizaje regularizacion sobreajuste validacion lote muestra clase etiqueta predictor modelo red "
              "convolucion filtro pooling recurrente memoria atencion token embedding").split()


def build_questions(levels=tuple(range(1, 11))):
    """50 valid, balanced questions: 5 true/false + 5 multiple choice per reading, distinct statements."""
    questions, number, per_kind = [], 0, {"true_false": 0, "multiple_choice": 0}
    for reading in READINGS:
        for kind in ("true_false",) * 5 + ("multiple_choice",) * 5:
            words = random.Random(number).sample(VOCABULARY, 8)       # distinct statements: no near duplicates
            options = ["Verdadero", "Falso"] if kind == "true_false" else [f"opcion {c} {number}" for c in "ABCD"]
            correct = options[per_kind[kind] % (2 if kind == "true_false" else 4)]   # alternate: balanced answers
            per_kind[kind] += 1
            questions.append({"id": f"q{number}", "reading": reading, "type": kind,
                              "statement": "Segun la lectura " + " ".join(words), "options": options,
                              "correct_option": correct, "difficulty_level": levels[number % len(levels)],
                              "source_quote": f"Cita literal de la lectura numero {number} del curso"})
            number += 1
    return questions


def grade(tmp_path, questions):
    config = load_config(CONFIG_FILE)
    path = tmp_path / "preguntas.json"
    path.write_text(json.dumps({"team": "t", "questions": questions}), encoding="utf-8")
    result = score(config, run_tests(config.test_file, path, tmp_path / "work"))
    return config, result, {s.key: s.points for s in result.scores}


def failed_names(result):
    return {name for name, _ in result.failures()}


def test_a_complete_balanced_submission_gets_the_maximum_grade(tmp_path):
    config, result, points = grade(tmp_path, build_questions())
    assert result.failures() == []
    assert final_grade(config, result.points) == 20
    assert points == {"count": 11, "format": 3, "difficulty": 3, "balance": 3}


def test_the_count_is_the_bulk_of_the_grade(tmp_path):
    config = load_config(CONFIG_FILE)
    assert next(c.points for c in config.criteria if c.key == "count") > config.maximum_grade / 2


def test_a_missing_question_costs_part_of_the_count_and_nothing_else(tmp_path):
    _, result, points = grade(tmp_path, build_questions()[:-1])
    assert 0 < points["count"] < 11
    assert points["format"] == 3 and points["balance"] == 3
    assert {"test_there_are_exactly_50_questions", "test_reading_has_5_questions_of_each_type"} <= failed_names(result)


def test_a_placeholder_left_is_a_missing_question_not_a_valid_one(tmp_path):
    questions = build_questions()
    questions[0]["source_quote"] = "PONGAN AQUÍ LA CITA TEXTUAL"
    _, result, points = grade(tmp_path, questions)
    assert {"test_no_template_placeholders_left", "test_there_are_exactly_50_questions"} <= failed_names(result)
    assert points["count"] < 11


def test_an_empty_list_scores_nothing_not_a_vacuous_pass(tmp_path):
    config, result, _ = grade(tmp_path, [])
    assert result.tests_passed == 0 and final_grade(config, result.points) == config.minimum_grade


def test_a_missing_file_scores_the_minimum(tmp_path):
    config = load_config(CONFIG_FILE)
    result = score(config, run_tests(config.test_file, tmp_path / "does-not-exist.json", tmp_path / "work"))
    assert result.tests_passed == 0 and final_grade(config, result.points) == config.minimum_grade


# --- Difficulty bands: 1-3, 4-6, 7-10 with at least 10 questions each ---

def test_exactly_10_questions_in_the_smallest_bands_still_pass(tmp_path):
    # 10 easy (1-3) + 10 medium (4-6) + 30 hard (7-10): the boundaries 3/4 and 6/7 are the ones that matter
    levels = [3] * 10 + [4] * 10 + [7] * 15 + [10] * 15
    _, result, points = grade(tmp_path, build_questions(levels=levels))
    assert points["difficulty"] == 3, result.failures()


def test_nine_in_a_band_loses_that_band_only(tmp_path):
    levels = [3] * 9 + [4] * 11 + [7] * 30          # easy 9 (< 10)
    _, result, points = grade(tmp_path, build_questions(levels=levels))
    assert points["difficulty"] == 2
    assert [name for name in failed_names(result)] == ["test_difficulty_band_has_at_least_10_questions"]


def test_concentrating_every_question_in_one_band_keeps_a_third_of_the_criterion(tmp_path):
    _, _, points = grade(tmp_path, build_questions(levels=(5,)))
    assert points["difficulty"] == 1


def test_level_zero_is_invalid_and_belongs_to_no_band(tmp_path):
    questions = build_questions()
    questions[0]["difficulty_level"] = 0
    _, result, _ = grade(tmp_path, questions)
    assert "test_difficulty_level_is_an_integer_between_1_and_10" in failed_names(result)


# --- Balance: the correct answer must not be guessable ---

def test_all_true_false_answers_verdadero_loses_half_the_balance(tmp_path):
    questions = build_questions()
    for q in questions:
        if q["type"] == "true_false":
            q["correct_option"] = "Verdadero"
    _, result, points = grade(tmp_path, questions)
    assert points["balance"] == 3 / 2 and failed_names(result) == {"test_true_false_answers_are_balanced"}


def test_always_the_same_multiple_choice_position_loses_half_the_balance(tmp_path):
    questions = build_questions()
    for q in questions:
        if q["type"] == "multiple_choice":
            q["correct_option"] = q["options"][0]
    _, result, points = grade(tmp_path, questions)
    assert points["balance"] == 3 / 2 and failed_names(result) == {"test_multiple_choice_correct_option_position_is_balanced"}


# --- Format rules, and the message must name the guilty question ---

@pytest.mark.parametrize("tweak, failing_test", [
    (lambda q: q.update(options=q["options"][:3], correct_option=q["options"][0]), "test_multiple_choice_has_exactly_4_options"),
    (lambda q: q.update(options=[q["options"][0], q["options"][0], "x", "y"]), "test_options_are_not_repeated_in_a_question"),
    (lambda q: q["options"].__setitem__(3, "Todas las anteriores"), "test_no_catch_all_options"),
    (lambda q: q["options"].__setitem__(3, "Ninguna de las opciones"), "test_no_catch_all_options"),
    (lambda q: q.update(statement="Muy corta"), "test_statements_have_at_least_5_words"),
    (lambda q: q.update(source_quote="corta"), "test_source_quote_is_a_real_quote"),
    (lambda q: q.pop("source_quote"), "test_required_fields_present"),
    (lambda q: q.update(reading="tuesday-week-1"), "test_reading_is_valid"),
])
def test_each_format_rule_fails_and_names_the_question(tmp_path, tweak, failing_test):
    questions = build_questions()
    target = next(q for q in questions if q["type"] == "multiple_choice")
    tweak(target)
    _, result, points = grade(tmp_path, questions)
    messages = dict(result.failures())
    assert failing_test in messages, f"{failing_test} did not fail: {sorted(messages)}"
    assert target["id"] in messages[failing_test]
    assert points["format"] < 3


def test_a_reworded_duplicate_statement_is_caught_as_a_near_duplicate(tmp_path):
    questions = build_questions()
    questions[1]["statement"] = questions[0]["statement"] + " ?"
    _, result, _ = grade(tmp_path, questions)
    assert "test_statements_are_not_duplicated" in failed_names(result)
    assert "q0 ~ q1" in dict(result.failures())["test_statements_are_not_duplicated"]
