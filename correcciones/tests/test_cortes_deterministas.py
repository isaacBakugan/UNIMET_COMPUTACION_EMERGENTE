"""Scoring of the deterministic cortes (corte-preguntas-2, 3, 4...) against synthetic submissions.

A corte is subject to everything here when its `corte.json` declares the deterministic criteria
(count, format, difficulty, balance): it is discovered by disk, so a new corte-preguntas-N that follows the
same standard is graded by these scenarios and gates without registering it anywhere.

The generic gates (every test belongs to a criterion, the untouched template scores the minimum) live in
test_corte.py and discover every correcciones/corte-*/corte.json by disk.
"""
import ast
import json
import random
import re
from pathlib import Path

import pytest

from corte import final_grade, load_config, run_tests, score

ROOT = Path(__file__).resolve().parent.parent.parent
DETERMINISTIC_KEYS = {"count", "format", "difficulty", "balance"}
VOCABULARY = ("perceptron gradiente neurona sesgo umbral capa peso activacion sigmoide frontera lineal entrenamiento "
              "epoca dataset vector matriz derivada error funcion salida entrada propagacion retropropagacion tasa "
              "aprendizaje regularizacion sobreajuste validacion lote muestra clase etiqueta predictor modelo red "
              "convolucion filtro pooling recurrente memoria atencion token embedding").split()


def valid_readings(test_file):
    """VALID_READINGS of a template test file, read from its source (no imports)."""
    for node in ast.parse(test_file.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "VALID_READINGS" for t in node.targets):
            return [element.value for element in node.value.elts]
    raise AssertionError(f"No VALID_READINGS in {test_file}")


def deterministic_configs():
    configs = []
    for path in sorted((ROOT / "correcciones").glob("corte-*/corte.json")):
        config = load_config(path)
        if {c.key for c in config.criteria} == DETERMINISTIC_KEYS:
            configs.append(config)
    return configs


CONFIGS = deterministic_configs()
TEMPLATE_TEST_FILES = sorted((ROOT / "repo-template").glob("corte-preguntas-*/tests/test_validar_entregable_*.py"))


class Corte:
    def __init__(self, config):
        self.config = config
        self.readings = valid_readings(config.test_file)
        self.total = 10 * len(self.readings)


@pytest.fixture(params=CONFIGS, ids=lambda config: config.folder)
def corte(request):
    return Corte(request.param)


def build_questions(corte, levels=tuple(range(1, 11))):
    """Valid, balanced questions: 5 true/false + 5 multiple choice per reading, distinct statements."""
    questions, number, per_kind = [], 0, {"true_false": 0, "multiple_choice": 0}
    for reading in corte.readings:
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


def grade(tmp_path, corte, questions):
    path = tmp_path / "preguntas.json"
    path.write_text(json.dumps({"team": "t", "questions": questions}), encoding="utf-8")
    result = score(corte.config, run_tests(corte.config.test_file, path, tmp_path / "work"))
    return result, {s.key: s.points for s in result.scores}


def failed_names(result):
    return {name for name, _ in result.failures()}


def points_of(corte, key):
    return next(c.points for c in corte.config.criteria if c.key == key)


# --- Gates discovered from disk: every deterministic corte shares the same standard ---

def normalized_rules(test_file):
    """The test source without what legitimately changes per corte: its readings and its question total."""
    source = test_file.read_text(encoding="utf-8").replace("\r\n", "\n")
    source = re.sub(r"VALID_READINGS = \{.*?\n\}", "VALID_READINGS = {...}", source, flags=re.S)
    return re.sub(r"exactly_\d+_questions", "exactly_N_questions", source)


def normalized_criteria(config):
    return [(c.key, c.points, sorted(re.sub(r"exactly_\d+_questions", "exactly_N_questions", t) for t in c.tests))
            for c in config.criteria]


def test_gate_discovers_deterministic_cortes():
    assert len(CONFIGS) >= 2, "Fewer than 2 deterministic cortes found: the sameness gates would prove nothing"


def test_gate_deterministic_cortes_share_the_same_rules_and_criteria():
    reference = CONFIGS[0]
    for config in CONFIGS[1:]:
        assert normalized_rules(config.test_file) == normalized_rules(reference.test_file), (
            f"{config.folder}: its tests differ from {reference.folder} beyond readings/total; same criteria means same rules"
        )
        assert normalized_criteria(config) == normalized_criteria(reference), (
            f"{config.folder}: criteria or points differ from {reference.folder}"
        )


def test_gate_a_reading_belongs_to_a_single_corte():
    assert TEMPLATE_TEST_FILES, "No template test files found"
    owner = {}
    for test_file in TEMPLATE_TEST_FILES:
        for reading in valid_readings(test_file):
            assert reading not in owner, f"Reading '{reading}' is in {owner[reading]} and in {test_file.parent.parent.name}"
            owner[reading] = test_file.parent.parent.name


def test_gate_the_template_has_exactly_the_questions_its_tests_ask_for():
    for config in CONFIGS:
        readings = valid_readings(config.test_file)
        template = json.loads((ROOT / "repo-template" / config.folder / config.deliverable).read_text(encoding="utf-8"))
        questions = template["questions"]
        assert template["assignment"] == config.folder, f"{config.folder}: wrong 'assignment' in the template"
        assert len({q["id"] for q in questions}) == len(questions), f"{config.folder}: duplicated ids in the template"
        for reading in readings:
            kinds = sorted(q["type"] for q in questions if q["reading"] == reading)
            assert kinds == ["multiple_choice"] * 5 + ["true_false"] * 5, f"{config.folder}/{reading}: {kinds}"
        assert {q["reading"] for q in questions} == set(readings), f"{config.folder}: readings of the template differ from the tests"


# --- Scoring scenarios, run against every deterministic corte ---

def test_a_complete_balanced_submission_gets_the_maximum_grade(tmp_path, corte):
    result, points = grade(tmp_path, corte, build_questions(corte))
    assert result.failures() == []
    assert final_grade(corte.config, result.points) == 20
    assert points == {c.key: c.points for c in corte.config.criteria}


def test_the_count_is_the_bulk_of_the_grade(corte):
    assert points_of(corte, "count") > corte.config.maximum_grade / 2


def test_a_missing_question_costs_part_of_the_count_and_nothing_else(tmp_path, corte):
    result, points = grade(tmp_path, corte, build_questions(corte)[:-1])
    assert 0 < points["count"] < points_of(corte, "count")
    assert points["format"] == points_of(corte, "format") and points["balance"] == points_of(corte, "balance")
    assert {f"test_there_are_exactly_{corte.total}_questions", "test_reading_has_5_questions_of_each_type"} <= failed_names(result)


def test_a_placeholder_left_is_a_missing_question_not_a_valid_one(tmp_path, corte):
    questions = build_questions(corte)
    questions[0]["source_quote"] = "PONGAN AQUÍ LA CITA TEXTUAL"
    result, points = grade(tmp_path, corte, questions)
    assert {"test_no_template_placeholders_left", f"test_there_are_exactly_{corte.total}_questions"} <= failed_names(result)
    assert points["count"] < points_of(corte, "count")


def test_an_empty_list_scores_nothing_not_a_vacuous_pass(tmp_path, corte):
    result, _ = grade(tmp_path, corte, [])
    assert result.tests_passed == 0 and final_grade(corte.config, result.points) == corte.config.minimum_grade


def test_a_missing_file_scores_the_minimum(tmp_path, corte):
    result = score(corte.config, run_tests(corte.config.test_file, tmp_path / "does-not-exist.json", tmp_path / "work"))
    assert result.tests_passed == 0 and final_grade(corte.config, result.points) == corte.config.minimum_grade


# --- Difficulty bands: 1-3, 4-6, 7-10 with at least 10 questions each ---

def test_exactly_10_questions_in_the_smallest_bands_still_pass(tmp_path, corte):
    # 10 easy (1-3) + 10 medium (4-6) + the rest hard (7-10): the boundaries 3/4 and 6/7 are the ones that matter
    rest = corte.total - 20
    levels = [3] * 10 + [4] * 10 + [7] * (rest // 2) + [10] * (rest - rest // 2)
    result, points = grade(tmp_path, corte, build_questions(corte, levels=levels))
    assert points["difficulty"] == points_of(corte, "difficulty"), result.failures()


def test_nine_in_a_band_loses_that_band_only(tmp_path, corte):
    levels = [3] * 9 + [4] * 11 + [7] * (corte.total - 20)          # easy 9 (< 10)
    result, points = grade(tmp_path, corte, build_questions(corte, levels=levels))
    assert points["difficulty"] == points_of(corte, "difficulty") * 2 / 3
    assert list(failed_names(result)) == ["test_difficulty_band_has_at_least_10_questions"]


def test_concentrating_every_question_in_one_band_keeps_a_third_of_the_criterion(tmp_path, corte):
    _, points = grade(tmp_path, corte, build_questions(corte, levels=(5,)))
    assert points["difficulty"] == points_of(corte, "difficulty") / 3


def test_level_zero_is_invalid_and_belongs_to_no_band(tmp_path, corte):
    questions = build_questions(corte)
    questions[0]["difficulty_level"] = 0
    result, _ = grade(tmp_path, corte, questions)
    assert "test_difficulty_level_is_an_integer_between_1_and_10" in failed_names(result)


# --- Balance: the correct answer must not be guessable ---

def test_all_true_false_answers_verdadero_loses_half_the_balance(tmp_path, corte):
    questions = build_questions(corte)
    for q in questions:
        if q["type"] == "true_false":
            q["correct_option"] = "Verdadero"
    result, points = grade(tmp_path, corte, questions)
    assert points["balance"] == points_of(corte, "balance") / 2 and failed_names(result) == {"test_true_false_answers_are_balanced"}


def test_always_the_same_multiple_choice_position_loses_half_the_balance(tmp_path, corte):
    questions = build_questions(corte)
    for q in questions:
        if q["type"] == "multiple_choice":
            q["correct_option"] = q["options"][0]
    result, points = grade(tmp_path, corte, questions)
    assert points["balance"] == points_of(corte, "balance") / 2
    assert failed_names(result) == {"test_multiple_choice_correct_option_position_is_balanced"}


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
def test_each_format_rule_fails_and_names_the_question(tmp_path, corte, tweak, failing_test):
    questions = build_questions(corte)
    target = next(q for q in questions if q["type"] == "multiple_choice")
    tweak(target)
    result, points = grade(tmp_path, corte, questions)
    messages = dict(result.failures())
    assert failing_test in messages, f"{failing_test} did not fail: {sorted(messages)}"
    assert target["id"] in messages[failing_test]
    assert points["format"] < points_of(corte, "format")


def test_a_reworded_duplicate_statement_is_caught_as_a_near_duplicate(tmp_path, corte):
    questions = build_questions(corte)
    questions[1]["statement"] = questions[0]["statement"] + " ?"
    result, _ = grade(tmp_path, corte, questions)
    assert "test_statements_are_not_duplicated" in failed_names(result)
    assert "q0 ~ q1" in dict(result.failures())["test_statements_are_not_duplicated"]
