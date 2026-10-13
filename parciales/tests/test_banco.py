"""Tests of the Moodle XML bank normalizer (parciales/banco.py) and its gates."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

import banco

ROOT = Path(__file__).resolve().parent.parent.parent


def question_xml(name="Pregunta", stem="Enunciado", options=(("Sí", 100), ("No", 0)), qtype="multichoice",
                 single="true", shuffle="true", extra=""):
    answers = "".join(f'<answer fraction="{fraction}"><text>{escape(text)}</text></answer>' for text, fraction in options)
    return (f'<question type="{qtype}"><name><text>{escape(name)}</text></name>'
            f'<questiontext format="html"><text>{escape(stem)}</text></questiontext>'
            f'<single>{single}</single><shuffleanswers>{shuffle}</shuffleanswers>{answers}{extra}</question>')


def category_xml(path):
    return f'<question type="category"><category><text>$course$/top/{path}</text></category></question>'


def write_export(tmp_path, *blocks):
    path = tmp_path / "export.xml"
    path.write_text('<?xml version="1.0" encoding="UTF-8"?><quiz>' + "".join(blocks) + "</quiz>", encoding="utf-8")
    return path


VF = category_xml("Verdadero o Falso/VF I Redes Neuronales/VF 1-Introducción")
TRUE_FALSE_OPTIONS = (("Verdadero", 100), ("Falso", 0))


def test_html_is_flattened_to_plain_text():
    text, flags = banco.to_plain_text("<p>H<sub>2</sub>O y x<sup>2</sup></p><ul><li>uno</li><li>dos</li></ul>a&amp;b<br>fin")
    assert text == "H₂O y x²\n\n- uno\n- dos\na&b\nfin"
    assert flags == set()


def test_html_review_flags_mark_what_plain_text_cannot_carry():
    assert "image" in banco.to_plain_text('<img src="x.png">')[1]
    assert "table" in banco.to_plain_text("<table><tr><td>1</td></tr></table>")[1]
    assert "layout" in banco.to_plain_text('<p style="padding-left: 40px;">pseudocódigo</p>')[1]
    assert "latex" in banco.to_plain_text("la fórmula \\(x^2\\)")[1]


@pytest.mark.parametrize("name, family", [
    ("Alan Turing 1", "alan turing"),
    ("Alan Turing 3", "alan turing"),
    ("Fitness combina error y utilidad (F)", "fitness combina error y utilidad"),
    ("Fitness combina error y utilidad (T)", "fitness combina error y utilidad"),
    ("Feature (definición desde nombre)", "feature"),
    ("Feature (nombre desde definición)", "feature"),
    ("Tamaños iguales (F1)", "tamaños iguales"),
    ("Sin marcador", "sin marcador"),
])
def test_variants_of_one_question_share_a_family_name(name, family):
    assert banco.family_name(name) == family


def test_a_nameless_question_is_its_own_family(tmp_path):
    export = write_export(tmp_path, VF,
                          question_xml(name="", stem="Uno", options=TRUE_FALSE_OPTIONS),
                          question_xml(name="", stem="Dos", options=TRUE_FALSE_OPTIONS))
    families = {q["family"] for q in banco.load_bank(export).ok}
    assert len(families) == 2


def test_id_survives_option_shuffles_and_changes_with_content():
    options = [{"text": "a", "correct": True}, {"text": "b", "correct": False}]
    assert banco.question_id("x", options) == banco.question_id("x", list(reversed(options)))
    assert banco.question_id("x", options) != banco.question_id("y", options)
    assert banco.question_id("x", options) != banco.question_id("x", [{"text": "a", "correct": False},
                                                                      {"text": "b", "correct": True}])


def test_unit_and_chapter_come_from_the_category_path():
    assert banco.parse_unit_and_chapter(["VF I Redes Neuronales", "VF 5-Multicapa", "VF 5.1.0 Def ML"]) == (
        "I Redes Neuronales", 5)
    assert banco.parse_unit_and_chapter(["Des. Hormigas +1"]) == (None, None)


@pytest.mark.parametrize("options, single, reason", [
    ((("a", 0), ("b", 0)), "true", "no_correct_answer"),
    ((("a", 100), ("b", 100)), "true", "multiple_correct_answers"),
    ((("a", 100), ("b", 0)), "false", "multiple_correct_answers"),
    ((("a", 100), ("A", 0)), "true", "duplicate_options"),
    ((("a", 100),), "true", "fewer_than_two_options"),
])
def test_questions_the_form_cannot_grade_are_quarantined_with_their_reason(tmp_path, options, single, reason):
    export = write_export(tmp_path, category_xml("Selección Simple/SS I Redes"),
                          question_xml(options=options, single=single))
    bank = banco.load_bank(export)
    assert bank.ok == []
    assert reason in bank.quarantined[0]["reasons"]


def test_true_false_must_be_binary(tmp_path):
    four = (("Verdadero", 100), ("Falso", 0), ("Ninguna", 0), ("Todas", 0))
    bank = banco.load_bank(write_export(tmp_path, VF, question_xml(options=four)))
    assert "true_false_not_binary" in bank.quarantined[0]["reasons"]


def test_name_suffix_contradicting_the_answer_key_is_a_warning_not_a_quarantine(tmp_path):
    export = write_export(tmp_path, VF, question_xml(name="Algo (T)", options=(("Verdadero", 0), ("Falso", 100))))
    bank = banco.load_bank(export)
    assert bank.quarantined == []
    assert bank.ok[0]["warnings"] == ["name_suffix_contradicts_answer"]


def test_a_repeated_question_is_quarantined_as_duplicate_content(tmp_path):
    export = write_export(tmp_path, VF, question_xml(name="A", options=TRUE_FALSE_OPTIONS),
                          category_xml("Verdadero o Falso/VF II Refuerzo"),
                          question_xml(name="B", options=TRUE_FALSE_OPTIONS))
    bank = banco.load_bank(export)
    assert len(bank.ok) == 1 and "duplicate_content" in bank.quarantined[0]["reasons"]


def test_nothing_is_dropped_silently(tmp_path):
    export = write_export(
        tmp_path, VF,
        question_xml(name="ok", stem="ok", options=TRUE_FALSE_OPTIONS),
        question_xml(name="sin correcta", stem="x", options=(("a", 0), ("b", 0))),
        question_xml(qtype="essay"),
        question_xml(qtype="description"),
        category_xml("Por defecto en plantilla_1"), question_xml(name="plantilla"),
        category_xml("Algo Nuevo/Sub"), question_xml(name="categoria desconocida", stem="y"),
    )
    bank = banco.load_bank(export)
    assert (len(bank.ok), len(bank.quarantined), len(bank.ignored)) == (1, 3, 2)
    reasons = {r for q in bank.quarantined for r in q["reasons"]}
    assert {"no_correct_answer", "unsupported_type:essay", "unknown_section"} <= reasons
    assert bank.report()["total"] == 6    # every <question> that is not a category marker


def test_an_export_without_questions_fails_instead_of_passing_green(tmp_path):
    with pytest.raises(ValueError):
        banco.load_bank(write_export(tmp_path, VF))


def test_embedded_images_are_extracted_next_to_the_bank(tmp_path):
    file_block = '<file name="sketch.png" path="/" encoding="base64">aGVsbG8=</file>'
    export = write_export(tmp_path, VF, question_xml(options=TRUE_FALSE_OPTIONS, extra=file_block))
    bank = banco.load_bank(export)
    banco.write_bank(bank, tmp_path / "out" / "banco.json", tmp_path / "out" / "imagenes")
    question = json.loads((tmp_path / "out" / "banco.json").read_text(encoding="utf-8"))["questions"][0]
    assert "image" in question["review_flags"] and question["image_files"] == ["sketch.png"]
    assert (tmp_path / "out" / "imagenes" / question["id"] / "sketch.png").read_bytes() == b"hello"


@pytest.mark.parametrize("path", ["parciales/banco/preguntas-x.xml", "parciales/specs/parcial-1.local.json",
                                  "parciales/specs/parcial-1.resuelto.local.json", "parciales/resultados/forms.json"])
def test_gate_sensitive_paths_are_git_ignored(path):
    """The bank carries the correct answers: a stray `git add .` must never publish it."""
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
    assert result.returncode == 0, f"{path} is not git-ignored; fix .gitignore"


def test_the_real_bank_reconciles_when_present():
    exports = sorted((ROOT / "parciales" / "banco").glob("preguntas-*.xml"))
    if not exports:
        pytest.skip("no Moodle export in parciales/banco/ (it is git-ignored)")
    report = banco.load_bank(exports[-1]).report()
    assert report["total"] == report["ok"] + report["quarantined"] + report["ignored"] > 0
