import json
import os
from collections import Counter
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
# The central grader points QUESTIONS_FILE at the team's file at the cutoff commit; students just run pytest.
QUESTIONS_FILE = Path(os.environ.get("QUESTIONS_FILE") or BASE_DIR / "preguntas.json")

VALID_TYPES = {"true_false", "multiple_choice"}
VALID_READINGS = {
    "tuesday-week-1",
    "thursday-week-1",
    "tuesday-week-2",
    "thursday-week-2",
}
REQUIRED_FIELDS = {"id", "reading", "type", "statement", "options", "correct_option", "difficulty_level"}

QUESTIONS_PER_READING = 10
EXPECTED_TOTAL = len(VALID_READINGS) * QUESTIONS_PER_READING

# At least MIN_PER_BAND easy questions (level < EASY_BELOW) and as many hard ones (level > HARD_ABOVE).
# DIFFICULTY_SCOPE "total": counted over the whole file. "reading": counted separately in each reading.
DIFFICULTY_SCOPE = "total"
EASY_BELOW = 3
HARD_ABOVE = 7
MIN_PER_BAND = 2

# Text the template ships with: a question that still has it was never written by the team.
PLACEHOLDER_STATEMENT_MARKER = "PONGAN AQUÍ"
PLACEHOLDER_OPTION_MARKER = "(edítenla)"


def is_placeholder(question):
    statement = str(question.get("statement", ""))
    options = question.get("options", [])
    return PLACEHOLDER_STATEMENT_MARKER in statement or any(
        PLACEHOLDER_OPTION_MARKER in str(option) for option in options
    )


def load_all_questions():
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def load_questions():
    """Questions the team actually wrote: template placeholders do not count as questions.

    Fails when there are none, so that no test passes "vacuously" over an empty or untouched file.
    """
    questions = [q for q in load_all_questions() if not is_placeholder(q)]
    assert questions, "No questions written yet: preguntas.json is empty or still has only the template placeholders"
    return questions


def questions_of(reading):
    return [q for q in load_questions() if q.get("reading") == reading]


def test_file_exists_and_is_valid_json():
    assert QUESTIONS_FILE.exists(), f"Missing {QUESTIONS_FILE.name}"
    load_questions()


def test_there_are_exactly_40_questions():
    questions = load_questions()
    assert len(questions) == EXPECTED_TOTAL, (
        f"Expected {EXPECTED_TOTAL} questions ({QUESTIONS_PER_READING} per reading x {len(VALID_READINGS)} readings), "
        f"got {len(questions)}"
    )


def test_no_template_placeholders_left():
    all_questions = load_all_questions()
    assert all_questions, "preguntas.json has no questions"   # an empty file must not pass "vacuously"
    placeholders = [q.get("id", "?") for q in all_questions if is_placeholder(q)]
    assert not placeholders, f"{len(placeholders)} questions still have the template text: {placeholders}"


def test_required_fields_present():
    for q in load_questions():
        missing = REQUIRED_FIELDS - q.keys()
        assert not missing, f"Question {q.get('id', '?')} is missing fields: {missing}"


def test_reading_is_valid():
    for q in load_questions():
        assert q["reading"] in VALID_READINGS, (
            f"Question {q.get('id', '?')}: invalid reading '{q.get('reading')}'"
        )


@pytest.mark.parametrize("reading", sorted(VALID_READINGS))
def test_reading_has_10_questions_5_true_false_and_5_multiple_choice(reading):
    from_this_reading = questions_of(reading)
    assert len(from_this_reading) == QUESTIONS_PER_READING, (
        f"Reading '{reading}': expected {QUESTIONS_PER_READING} questions, got {len(from_this_reading)}"
    )

    counts = Counter(q.get("type") for q in from_this_reading)
    assert counts["true_false"] == 5, (
        f"Reading '{reading}': expected 5 true/false, got {counts['true_false']}"
    )
    assert counts["multiple_choice"] == 5, (
        f"Reading '{reading}': expected 5 multiple choice, got {counts['multiple_choice']}"
    )


def test_types_are_valid():
    for q in load_questions():
        assert q.get("type") in VALID_TYPES, f"Invalid type in {q.get('id', '?')}: {q.get('type')}"


def test_statements_are_not_empty():
    for q in load_questions():
        assert q["statement"].strip(), f"Question {q.get('id', '?')} has an empty statement"


def test_statements_are_not_duplicated():
    questions = load_questions()
    statements = [q["statement"].strip().lower() for q in questions]
    duplicates = {s for s in statements if statements.count(s) > 1}
    assert not duplicates, f"Duplicate statements: {duplicates}"


def test_correct_option_is_in_options():
    for q in load_questions():
        assert q["correct_option"] in q["options"], (
            f"Question {q.get('id', '?')}: correct_option is not in options"
        )


def test_true_false_has_the_2_correct_options():
    for q in load_questions():
        if q["type"] == "true_false":
            assert set(q["options"]) == {"Verdadero", "Falso"}, (
                f"Question {q.get('id', '?')}: true/false options must be exactly Verdadero/Falso"
            )


def test_multiple_choice_has_at_least_3_options():
    for q in load_questions():
        if q["type"] == "multiple_choice":
            assert len(q["options"]) >= 3, (
                f"Question {q.get('id', '?')}: multiple choice must have at least 3 options"
            )


def test_difficulty_level_is_an_integer_between_1_and_10():
    for q in load_questions():
        level = q["difficulty_level"]
        assert isinstance(level, int) and not isinstance(level, bool), (
            f"Question {q.get('id', '?')}: difficulty_level must be an integer"
        )
        assert 1 <= level <= 10, f"Question {q.get('id', '?')}: difficulty_level must be between 1 and 10"


DIFFICULTY_SCOPES = sorted(VALID_READINGS) if DIFFICULTY_SCOPE == "reading" else ["all"]


def difficulty_levels(scope):
    questions = load_questions() if scope == "all" else questions_of(scope)
    return [q["difficulty_level"] for q in questions
            if isinstance(q.get("difficulty_level"), int) and not isinstance(q.get("difficulty_level"), bool)]


def scope_label(scope):
    return "the file" if scope == "all" else f"reading '{scope}'"


@pytest.mark.parametrize("scope", DIFFICULTY_SCOPES)
def test_has_at_least_2_easy_questions(scope):
    easy = [level for level in difficulty_levels(scope) if level < EASY_BELOW]
    assert len(easy) >= MIN_PER_BAND, (
        f"In {scope_label(scope)}: need at least {MIN_PER_BAND} easy questions "
        f"(difficulty_level < {EASY_BELOW}), got {len(easy)}"
    )


@pytest.mark.parametrize("scope", DIFFICULTY_SCOPES)
def test_has_at_least_2_hard_questions(scope):
    hard = [level for level in difficulty_levels(scope) if level > HARD_ABOVE]
    assert len(hard) >= MIN_PER_BAND, (
        f"In {scope_label(scope)}: need at least {MIN_PER_BAND} hard questions "
        f"(difficulty_level > {HARD_ABOVE}), got {len(hard)}"
    )
