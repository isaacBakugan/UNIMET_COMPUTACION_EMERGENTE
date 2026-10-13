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
    template = ROOT / "repo-template" / config.folder / config.deliverable   # each corte ships its own template
    assert template.exists(), f"Missing template {template}"
    result = grade_file(config, template, tmp_path)
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


# --- Late policy: lateness is INDIVIDUAL (by commit author), the deliverable is the team's ---

def commit_file(repo, content, date, message, email):
    import os
    import subprocess
    folder = repo / "corte-preguntas-1"
    folder.mkdir(exist_ok=True)
    (folder / "preguntas.json").write_text(content, encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": email}
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=True, capture_output=True, env=env)


def evaluate_in_temp_repo(tmp_path, on_time_content, late_content, late_email="Late@Example.com"):
    import subprocess
    from dataclasses import replace
    from calificador_corte import evaluate_team
    repo = tmp_path / "clones" / "team-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    commit_file(repo, on_time_content, "2026-09-27T12:00:00-04:00", "on time", "ontime@example.com")
    if late_content is not None:
        commit_file(repo, late_content, "2026-09-29T12:00:00-04:00", "late", late_email)
    config = replace(load_config(CONFIG_FILES[0]), cutoff="2026-09-28T00:00:00-04:00")
    item = {"team": "T", "repo": "team-repo", "url": "https://example.invalid/team-repo"}
    return config, evaluate_team(item, config, tmp_path / "clones", tmp_path / "work", update=False)


def questions_json(questions):
    return json.dumps({"team": "t", "questions": questions})


def test_the_student_who_pushed_late_gets_the_penalized_version_and_teammates_keep_the_cutoff_grade(tmp_path):
    from calificador_corte import student_grade
    template = TEMPLATE_QUESTIONS.read_text(encoding="utf-8")
    config, row = evaluate_in_temp_repo(tmp_path, template, questions_json(full_submission()))
    assert row.late_emails == {"late@example.com"}          # authors are compared in lowercase
    assert student_grade(row, config, is_late=True) == (18, True)    # 20 - 2
    assert student_grade(row, config, is_late=False) == (config.minimum_grade, False)


def test_a_late_commit_never_hurts_the_author(tmp_path):
    from calificador_corte import student_grade
    full = questions_json(full_submission())
    late_tweak = full.replace('"team": "t"', '"team": "t2"')   # same questions, different file
    config, row = evaluate_in_temp_repo(tmp_path, full, late_tweak)
    assert student_grade(row, config, is_late=True) == (20, False)   # on-time 20 beats late 20 - 2


def test_no_late_commits_means_no_latest_version_and_no_penalty(tmp_path):
    from calificador_corte import student_grade
    config, row = evaluate_in_temp_repo(tmp_path, questions_json(full_submission()), None)
    assert row.latest_result is None and row.late_commits == []
    assert student_grade(row, config, is_late=True) == (20, False)


def test_student_rows_penalize_only_the_mapped_late_author_and_warn_about_unmapped_ones(tmp_path):
    from calificador_corte import student_rows
    from lista import ListEntry
    template = TEMPLATE_QUESTIONS.read_text(encoding="utf-8")
    entries = [ListEntry("Alfa", "Ana", "T"), ListEntry("Beta", "Beto", "T")]
    config, row = evaluate_in_temp_repo(tmp_path, template, questions_json(full_submission()), late_email="ana@example.com")
    warnings = []
    rows = student_rows(entries, [row], config, {"ana@example.com": ("Alfa", "Ana")}, warnings)
    assert [(r["Apellido"], r["Nota"]) for r in rows] == [("Alfa", 18), ("Beta", config.minimum_grade)]
    assert "Entrega tardía" in rows[0]["Observación"] and rows[1]["Observación"] == ""
    assert warnings == []

    warnings = []
    rows = student_rows(entries, [row], config, {}, warnings)    # nobody is mapped to the late author
    assert [r["Nota"] for r in rows] == [config.minimum_grade, config.minimum_grade]
    assert any("ana@example.com" in w and "autores.csv" in w for w in warnings)


@pytest.mark.parametrize("config_file", CONFIG_FILES, ids=lambda path: path.parent.name)
def test_gate_every_author_maps_to_a_student_of_the_delivery_list(config_file):
    import csv
    from calificador_corte import load_authors
    from lista import normalize
    authors = load_authors(config_file.parent / "autores.csv")
    assert authors, "Empty autores.csv: the gate would pass without proving anything"
    with (ROOT / "trimestre-actual" / "lista-entrega.csv").open(newline="", encoding="utf-8-sig") as file:
        listed = {(normalize(r["last_name"]), normalize(r["first_name"])) for r in csv.DictReader(file)}
    unknown = {email: name for email, name in authors.items() if (normalize(name[0]), normalize(name[1])) not in listed}
    assert not unknown, f"Authors that do not match anyone in lista-entrega.csv: {unknown}"
