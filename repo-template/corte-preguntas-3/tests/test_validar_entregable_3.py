import difflib
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
# The central grader points QUESTIONS_FILE at the team's file at the cutoff commit; students just run pytest.
QUESTIONS_FILE = Path(os.environ.get("QUESTIONS_FILE") or BASE_DIR / "preguntas.json")

VALID_TYPES = ("true_false", "multiple_choice")
VALID_READINGS = {
    "tuesday-week-7",
    "thursday-week-7",
    "tuesday-week-8",
    "thursday-week-8",
}
REQUIRED_FIELDS = {"id", "reading", "type", "statement", "options", "correct_option", "difficulty_level", "source_quote"}

QUESTIONS_PER_TYPE = 5
QUESTIONS_PER_READING = QUESTIONS_PER_TYPE * len(VALID_TYPES)
EXPECTED_TOTAL = len(VALID_READINGS) * QUESTIONS_PER_READING

# Difficulty bands (inclusive), counted over the whole file: at least MIN_PER_BAND questions in each one.
DIFFICULTY_BANDS = {"easy": (1, 3), "medium": (4, 6), "hard": (7, 10)}
MIN_PER_BAND = 10

MULTIPLE_CHOICE_OPTIONS = 4
MIN_STATEMENT_WORDS = 5
MIN_SOURCE_QUOTE_CHARS = 20
MAX_STATEMENT_SIMILARITY = 0.85

# Answer patterns that can be guessed without reading anything.
TRUE_SHARE_RANGE = (0.4, 0.6)            # share of "Verdadero" among the true/false answers
MAX_SHARE_PER_CORRECT_POSITION = 0.5     # share of multiple choice whose correct option sits in the same position
CATCH_ALL_OPTION = re.compile(r"\b(todas|ninguna)\s+(de\s+)?(las\s+)?(anteriores|opciones)\b")

# Text the template ships with: a question that still has it was never written by the team.
PLACEHOLDER_MARKER = "PONGAN AQUÍ"
PLACEHOLDER_OPTION_MARKER = "(edítenla)"


def normalize(text):
    """Lowercase, no accents, single spaces: so that 'Más' and 'mas ' compare equal."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).lower().split())


def is_placeholder(question):
    texts = [question.get("statement", ""), question.get("source_quote", "")]
    return any(PLACEHOLDER_MARKER in str(text) for text in texts) or any(
        PLACEHOLDER_OPTION_MARKER in str(option) for option in question.get("options", [])
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


def questions_of_type(kind):
    """Written questions of one type; fails when there are none so balance checks never pass over nothing."""
    questions = [q for q in load_questions() if q.get("type") == kind]
    assert questions, f"No {kind} questions written yet"
    return questions


def label(question):
    return question.get("id", "?")


def assert_no_problems(problems, summary):
    assert not problems, f"{summary}: " + "; ".join(problems)


# --- Count: all the requested questions (the bulk of the grade) ---

def test_there_are_exactly_40_questions():
    questions = load_questions()
    assert len(questions) == EXPECTED_TOTAL, (
        f"Expected {EXPECTED_TOTAL} questions ({QUESTIONS_PER_READING} per reading x {len(VALID_READINGS)} readings), "
        f"got {len(questions)}"
    )


@pytest.mark.parametrize("reading", sorted(VALID_READINGS))
@pytest.mark.parametrize("kind", VALID_TYPES)
def test_reading_has_5_questions_of_each_type(reading, kind):
    written = [q for q in load_questions() if q.get("reading") == reading and q.get("type") == kind]
    assert len(written) == QUESTIONS_PER_TYPE, (
        f"Reading '{reading}': expected {QUESTIONS_PER_TYPE} {kind} questions, got {len(written)}"
    )


# --- Format ---

def test_file_exists_and_is_valid_json():
    assert QUESTIONS_FILE.exists(), f"Missing {QUESTIONS_FILE.name}"
    load_questions()


def test_no_template_placeholders_left():
    all_questions = load_all_questions()
    assert all_questions, "preguntas.json has no questions"   # an empty file must not pass "vacuously"
    placeholders = [label(q) for q in all_questions if is_placeholder(q)]
    assert not placeholders, f"{len(placeholders)} questions still have the template text: {placeholders}"


def test_required_fields_present():
    problems = [f"{label(q)} lacks {sorted(REQUIRED_FIELDS - q.keys())}" for q in load_questions()
                if REQUIRED_FIELDS - q.keys()]
    assert_no_problems(problems, "Questions with missing fields")


def test_reading_is_valid():
    problems = [f"{label(q)} has '{q.get('reading')}'" for q in load_questions() if q.get("reading") not in VALID_READINGS]
    assert_no_problems(problems, "Invalid reading")


def test_types_are_valid():
    problems = [f"{label(q)} has '{q.get('type')}'" for q in load_questions() if q.get("type") not in VALID_TYPES]
    assert_no_problems(problems, "Invalid type")


def test_statements_have_at_least_5_words():
    problems = [label(q) for q in load_questions() if len(str(q.get("statement", "")).split()) < MIN_STATEMENT_WORDS]
    assert_no_problems(problems, f"Statements shorter than {MIN_STATEMENT_WORDS} words")


def test_statements_are_not_duplicated():
    """Exact or near duplicates (similarity >= MAX_STATEMENT_SIMILARITY): the same fact asked twice."""
    questions = load_questions()
    statements = [normalize(q.get("statement", "")) for q in questions]
    problems = []
    for first in range(len(questions)):
        for second in range(first + 1, len(questions)):
            ratio = difflib.SequenceMatcher(None, statements[first], statements[second]).ratio()
            if ratio >= MAX_STATEMENT_SIMILARITY:
                problems.append(f"{label(questions[first])} ~ {label(questions[second])} ({ratio:.0%})")
    assert_no_problems(problems, f"Duplicated or near-duplicated statements (>= {MAX_STATEMENT_SIMILARITY:.0%})")


def test_correct_option_is_in_options():
    problems = [label(q) for q in load_questions() if q.get("correct_option") not in q.get("options", [])]
    assert_no_problems(problems, "correct_option is not in options")


def test_true_false_has_the_2_correct_options():
    problems = [label(q) for q in load_questions()
                if q.get("type") == "true_false" and set(q.get("options", [])) != {"Verdadero", "Falso"}]
    assert_no_problems(problems, "true/false options must be exactly Verdadero/Falso")


def test_multiple_choice_has_exactly_4_options():
    problems = [f"{label(q)} has {len(q.get('options', []))}" for q in load_questions()
                if q.get("type") == "multiple_choice" and len(q.get("options", [])) != MULTIPLE_CHOICE_OPTIONS]
    assert_no_problems(problems, f"Multiple choice must have exactly {MULTIPLE_CHOICE_OPTIONS} options")


def test_options_are_not_repeated_in_a_question():
    """No two equal options, and no option that just repeats the statement."""
    problems = []
    for q in load_questions():
        options = [normalize(option) for option in q.get("options", [])]
        if len(set(options)) != len(options):
            problems.append(f"{label(q)} repeats an option")
        elif q.get("type") == "multiple_choice" and normalize(q.get("statement", "")) in options:
            problems.append(f"{label(q)} has an option equal to the statement")
    assert_no_problems(problems, "Repeated options")


def test_no_catch_all_options():
    """'Todas las anteriores' / 'Ninguna de las anteriores' are guessed without understanding the reading."""
    problems = [label(q) for q in load_questions()
                if any(CATCH_ALL_OPTION.search(normalize(option)) for option in q.get("options", []))]
    assert_no_problems(problems, "Catch-all options (todas / ninguna de las anteriores)")


def test_difficulty_level_is_an_integer_between_1_and_10():
    problems = [f"{label(q)} has {q.get('difficulty_level')!r}" for q in load_questions()
                if not is_valid_level(q.get("difficulty_level"))]
    assert_no_problems(problems, "difficulty_level must be an integer between 1 and 10")


def test_source_quote_is_a_real_quote():
    """A literal fragment of the reading that justifies the correct answer (checked against the reading later)."""
    problems = [label(q) for q in load_questions()
                if len(str(q.get("source_quote", "")).strip()) < MIN_SOURCE_QUOTE_CHARS]
    assert_no_problems(problems, f"source_quote must have at least {MIN_SOURCE_QUOTE_CHARS} characters")


# --- Difficulty: a spread of levels, not a pile in one band ---

def is_valid_level(level):
    return isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= 10


@pytest.mark.parametrize("band", list(DIFFICULTY_BANDS))
def test_difficulty_band_has_at_least_10_questions(band):
    low, high = DIFFICULTY_BANDS[band]
    in_band = [q for q in load_questions() if is_valid_level(q.get("difficulty_level")) and low <= q["difficulty_level"] <= high]
    assert len(in_band) >= MIN_PER_BAND, (
        f"Band '{band}' (difficulty_level {low} to {high}): need at least {MIN_PER_BAND} questions, got {len(in_band)}"
    )


# --- Balance: the correct answer must not be predictable ---

def test_true_false_answers_are_balanced():
    answers = [q.get("correct_option") for q in questions_of_type("true_false")]
    share = answers.count("Verdadero") / len(answers)
    low, high = TRUE_SHARE_RANGE
    assert low <= share <= high, (
        f"{answers.count('Verdadero')} of {len(answers)} true/false answers are 'Verdadero' ({share:.0%}); "
        f"keep it between {low:.0%} and {high:.0%}"
    )


def test_multiple_choice_correct_option_position_is_balanced():
    positions = [q["options"].index(q["correct_option"]) for q in questions_of_type("multiple_choice")
                 if isinstance(q.get("options"), list) and q.get("correct_option") in q["options"]]
    assert positions, "No multiple choice question has its correct_option among its options"
    position, count = Counter(positions).most_common(1)[0]
    assert count / len(positions) <= MAX_SHARE_PER_CORRECT_POSITION, (
        f"The correct answer is option {chr(65 + position)} in {count} of {len(positions)} multiple choice questions "
        f"({count / len(positions):.0%}); at most {MAX_SHARE_PER_CORRECT_POSITION:.0%} may share the same position"
    )
