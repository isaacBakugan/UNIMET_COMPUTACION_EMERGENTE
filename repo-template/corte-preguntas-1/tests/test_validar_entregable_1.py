import json
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = BASE_DIR / "preguntas.json"

VALID_TYPES = {"true_false", "multiple_choice"}
VALID_READINGS = {
    "tuesday-week-1",
    "thursday-week-1",
    "tuesday-week-2",
    "thursday-week-2",
}
REQUIRED_FIELDS = {"id", "reading", "type", "statement", "options", "correct_option", "difficulty_level"}

EXPECTED_TOTAL = len(VALID_READINGS) * 10


def load_questions():
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def test_file_exists_and_is_valid_json():
    assert QUESTIONS_FILE.exists(), f"Missing {QUESTIONS_FILE.name}"
    load_questions()


def test_there_are_exactly_40_questions():
    questions = load_questions()
    assert len(questions) == EXPECTED_TOTAL, (
        f"Expected {EXPECTED_TOTAL} questions (10 per reading x {len(VALID_READINGS)} readings), "
        f"got {len(questions)}"
    )


def test_required_fields_present():
    for q in load_questions():
        missing = REQUIRED_FIELDS - q.keys()
        assert not missing, f"Question {q.get('id', '?')} is missing fields: {missing}"


def test_reading_is_valid():
    for q in load_questions():
        assert q["reading"] in VALID_READINGS, (
            f"Question {q.get('id', '?')}: invalid reading '{q.get('reading')}'"
        )


def test_10_questions_per_reading_5_true_false_and_5_multiple_choice():
    questions = load_questions()
    for reading in VALID_READINGS:
        from_this_reading = [q for q in questions if q.get("reading") == reading]
        assert len(from_this_reading) == 10, (
            f"Reading '{reading}': expected 10 questions, got {len(from_this_reading)}"
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
