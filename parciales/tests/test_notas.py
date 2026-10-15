"""Tests of the grades of an exam from its Form responses (parciales/notas.py) and of the scoring in the export (Code.gs)."""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

import notas
import publicar
from lista import ListEntry

ROOT = Path(__file__).resolve().parent.parent.parent
APPS_SCRIPT = ROOT / "parciales" / "apps-script"

ENTRIES = [ListEntry("Arrieta", "Andrés", "Cyberleak"), ListEntry("Girón", "Verónica", "Aris"),
           ListEntry("Pérez", "Ana", "LUMON"), ListEntry("Pérez", "Luis", "LUMON")]

# Google's scaled integers: 2 + 2 + 6 = 10 points, so a perfect exam is 20 and every point is worth 2 of base 20
PAYLOAD = {"key": "k1", "sections": [
    {"title": "VF", "questions": [
        {"stem": "El perceptrón\nes lineal.", "points": 2, "options": [{"text": "Verdadero", "correct": True}, {"text": "Falso", "correct": False}]},
        {"stem": "La red olvida.", "points": 2, "options": [{"text": "Verdadero", "correct": False}, {"text": "Falso", "correct": True}]}]},
    {"title": "D", "questions": [
        {"stem": "¿Cuál es la salida?", "points": 6, "options": [{"text": "[1, 2]", "correct": False}, {"text": "[3, 6]", "correct": True}]}]}]}


def response(first, last, score=10, email=None, timestamp="2026-10-14T10:00:00.000Z", id_number="12345678"):
    return {"timestamp": timestamp, "email": email or f"{first}.{last}@correo.unimet.edu.ve".lower(), "score": score,
            "identification": {"Apellidos": last, "Nombres": first, "Cédula de identidad": id_number}}


def submissions(*responses, key="k1"):
    return notas.load_submissions({"exam_key": key, "responses": list(responses)}, PAYLOAD)


def grade_table(*responses, entries=ENTRIES):
    subs = submissions(*responses)
    counted = notas.assign(subs, entries)
    return notas.student_rows(entries, counted), subs, counted


def test_the_grade_is_the_points_over_the_maximum_in_base_20():
    assert notas.to_grade(Fraction(62), Fraction(80)) == Fraction("15.5")    # 80 points x4 -> divide by 4
    assert notas.to_grade(Fraction(80), Fraction(80)) == 20
    assert notas.to_grade(Fraction(0), Fraction(80)) == 0
    assert notas.to_grade(Fraction(61), Fraction(80)) == Fraction("15.25")


def test_grades_are_written_with_a_decimal_comma_and_no_trailing_zeros():
    assert [notas.format_grade(Fraction(x)) for x in ("15.25", "17", "15.5", "0")] == ["15,25", "17", "15,5", "0"]


def test_a_grade_with_a_decimal_comma_stays_in_one_csv_cell(tmp_path):
    rows = [{"Apellido": "Arrieta", "Nombre": "Andrés", "Equipo": "Cyberleak", "Nota": notas.format_grade(Fraction("15.25")), "Observación": ""}]
    notas.write_outputs(rows, [], Fraction(10), tmp_path)
    text = (tmp_path / "notas-sheets.csv").read_text(encoding="utf-8-sig")
    assert '"15,25"' in text    # quoted, so the comma is not read as a column separator
    with (tmp_path / "notas-sheets.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert list(csv.DictReader(handle))[0]["Nota"] == "15,25"


def test_a_response_without_a_score_is_refused_not_read_as_zero():
    # the bug this guards: a null score coerced to 0 put a 0 on every student
    with pytest.raises(publicar.PublishError, match="no score"):
        submissions(response("Andrés", "Arrieta", score=None))


def test_a_score_above_the_maximum_means_the_file_is_not_of_this_exam():
    with pytest.raises(publicar.PublishError, match="above the maximum"):
        submissions(response("Andrés", "Arrieta", score=11))


def test_responses_of_another_exam_are_refused():
    with pytest.raises(publicar.PublishError, match="another exam"):
        submissions(response("Andrés", "Arrieta"), key="other")


def test_the_rows_follow_the_order_of_the_delivery_list_not_the_order_of_the_responses():
    rows, _, _ = grade_table(response("Verónica", "Girón", 8), response("Andrés", "Arrieta", 10))
    assert [r["Apellido"] for r in rows] == ["Arrieta", "Girón", "Pérez", "Pérez"]
    assert [r["Nota"] for r in rows] == ["20", "16", "", ""]


def test_someone_on_the_list_who_did_not_answer_has_an_empty_grade_and_a_note_not_a_zero():
    rows, _, _ = grade_table(response("Andrés", "Arrieta"))
    missing = [r for r in rows if r["Apellido"] == "Girón"][0]
    assert missing["Nota"] == "" and "Sin respuesta" in missing["Observación"]


def test_names_match_without_accents_case_or_extra_surnames():
    rows, _, _ = grade_table(response("ANDRES", "arrieta"), response("Verónica Del Valle", "Girón Rojas", 8))
    assert [r["Nota"] for r in rows[:2]] == ["20", "16"]


def test_a_respondent_not_on_the_list_is_reported_and_kept_out_of_the_sheet():
    rows, subs, counted = grade_table(response("Pedro", "Intruso", email="pedro@x.ve"))
    assert all(r["Nota"] == "" for r in rows)
    assert subs[0].match == notas.NOT_ON_LIST
    assert any("pedro@x.ve" in w and "asignar a mano" in w for w in notas.warnings_of(ENTRIES, subs, counted))


def test_an_ambiguous_name_is_never_guessed():
    # "Pérez" alone fits both Pérez of the list
    rows, subs, counted = grade_table(response("", "Pérez"))
    assert subs[0].match == notas.AMBIGUOUS and counted == {}
    assert any("más de una entrada" in w for w in notas.warnings_of(ENTRIES, subs, counted))


def test_a_name_that_fits_one_entry_exactly_wins_over_a_looser_match():
    entries = [ListEntry("Pérez", "Ana", "A"), ListEntry("Pérez", "Ana María", "B")]
    rows, subs, _ = grade_table(response("Ana", "Pérez"), entries=entries)
    assert subs[0].entry == entries[0] and rows[0]["Nota"] == "20"


def test_a_blank_name_matches_nobody():
    _, subs, counted = grade_table(response("", ""))
    assert subs[0].match == notas.NOT_ON_LIST and counted == {}


def test_two_responses_of_one_student_count_the_earliest_and_are_flagged():
    rows, subs, counted = grade_table(
        response("Andrés", "Arrieta", 0, email="b@x.ve", timestamp="2026-10-14T11:00:00.000Z"),
        response("Andrés", "Arrieta", 10, email="a@x.ve", timestamp="2026-10-14T10:00:00.000Z"))
    assert rows[0]["Nota"] == "20" and "2 respuestas" in rows[0]["Observación"]
    assert [s.match for s in subs] == [notas.MATCHED, "duplicate"]
    assert any("solo la primera" in w for w in notas.warnings_of(ENTRIES, subs, counted))


def test_outputs_have_the_sheet_columns_and_a_detail_row_per_response(tmp_path):
    rows, subs, _ = grade_table(response("Andrés", "Arrieta", 8), response("Pedro", "Intruso", 0))
    notas.write_outputs(rows, subs, Fraction(10), tmp_path)
    with (tmp_path / "notas-sheets.csv").open(encoding="utf-8-sig", newline="") as handle:
        sheet = list(csv.DictReader(handle))
    assert list(sheet[0]) == ["Apellido", "Nombre", "Equipo", "Nota", "Observación"]
    assert (sheet[0]["Apellido"], sheet[0]["Nota"]) == ("Arrieta", "16") and len(sheet) == len(ENTRIES)
    with (tmp_path / "notas.csv").open(encoding="utf-8-sig", newline="") as handle:
        detail = list(csv.DictReader(handle))
    assert {d["match"] for d in detail} == {notas.MATCHED, notas.NOT_ON_LIST} and len(detail) == 2
    matched = [d for d in detail if d["match"] == notas.MATCHED][0]
    assert (matched["email"], matched["id_number"], matched["points"], matched["grade"]) == ("andrés.arrieta@correo.unimet.edu.ve", "12345678", "8", "16")


def test_main_end_to_end_from_the_exported_json(tmp_path, monkeypatch, capsys):
    """Resolved exam -> payload key and maximum -> responses file -> the two CSVs and the console report."""
    bank = {"questions": [
        {"id": "q001", "name": "P1", "section": "true_false", "category": "X", "family": "x|1", "stem": "e1", "shuffle_options": False,
         "image_files": [], "review_flags": [], "options": [{"text": "Verdadero", "correct": True}, {"text": "Falso", "correct": False}]},
        {"id": "q002", "name": "P2", "section": "development", "category": "X", "family": "x|2", "stem": "e2", "shuffle_options": False,
         "image_files": [], "review_flags": [], "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]}]}
    sections = [{"title": "VF", "section": "true_false", "points": 0.5, "questions": [{"id": "q001", "name": "x"}]},
                {"title": "D", "section": "development", "points": 2.5, "questions": [{"id": "q002", "name": "x"}]}]
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "examen.resuelto.local.json").write_text(json.dumps({"title": "e", "mode": "real", "sections": sections}), encoding="utf-8")
    (tmp_path / "banco.json").write_text(json.dumps(bank), encoding="utf-8")
    monkeypatch.setattr(notas, "SPECS_DIR", specs)
    key = publicar.build_payload("examen", bank, specs, tmp_path / "banco.json")["key"]    # 0.5 and 2.5 -> x2: 1 + 5, maximum 6
    (tmp_path / "list.csv").write_text("last_name,first_name,team\nArrieta,Andrés,Cyberleak\nGirón,Verónica,Aris\n", encoding="utf-8")
    export = tmp_path / "respuestas.json"
    export.write_text(json.dumps({"exam_key": key, "responses": [response("Andrés", "Arrieta", 1)]}), encoding="utf-8")

    code = notas.main(["examen", "--responses", str(export), "--list", str(tmp_path / "list.csv"), "--bank", str(tmp_path / "banco.json")])

    out = capsys.readouterr().out
    assert code == 0 and "1/2 students" in out and "Girón" in out    # the one without response is reported
    with (tmp_path / "notas-sheets.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert [r["Nota"] for r in csv.DictReader(handle)] == ["3,33", ""]    # 1 of 6 points -> 3,33 of 20


def test_main_says_where_to_get_the_responses_when_the_file_is_missing(tmp_path, capsys):
    assert notas.main(["examen", "--responses", str(tmp_path / "nope.json")]) == 1
    assert "exportResponsesReal" in capsys.readouterr().out


# --- the scoring of the export lives in Code.gs (JavaScript): it runs with node on cases whose points are written by hand ---

NODE_DRIVER = """
const vm = require('vm'), fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(input.code_file, 'utf8') + '\\n;this.api = {questionIndex_, scoreItems_};', context);
try {
  const questions = context.api.questionIndex_(input.payload);
  process.stdout.write(JSON.stringify({points: context.api.scoreItems_(questions, input.items, 'student@x.ve')}));
} catch (error) {
  process.stdout.write(JSON.stringify({error: error.message}));
}
"""


def score_in_js(items, payload=PAYLOAD):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is not on the PATH: the scoring of Code.gs cannot be tested (it ships with clasp, which needs it)")
    result = subprocess.run([node, "-e", NODE_DRIVER], input=json.dumps({"code_file": str(APPS_SCRIPT / "Code.gs"), "payload": payload, "items": items}),
                            capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def items(*answers):
    return [{"title": title, "response": chosen} for title, chosen in answers]


@pytest.mark.parametrize("answers, points", [
    ([("El perceptrón\nes lineal.", "Verdadero"), ("La red olvida.", "Falso"), ("¿Cuál es la salida?", "[3, 6]")], 10),    # perfect
    ([("El perceptrón\nes lineal.", "Verdadero"), ("La red olvida.", "Verdadero"), ("¿Cuál es la salida?", "[3, 6]")], 8),    # one wrong
    ([("El perceptrón\nes lineal.", "Falso"), ("La red olvida.", "Verdadero"), ("¿Cuál es la salida?", "[1, 2]")], 0),    # all wrong
    ([("El  perceptrón   es lineal.", " Verdadero "), ("La red olvida.", "Falso"), ("¿Cuál es la salida?", "[3, 6]")], 10),    # Google rewraps whitespace
    ([("El perceptrón\nes lineal.", "Verdadero"), ("La red olvida.", "Falso")], 4),    # an unanswered question adds nothing
])
def test_the_export_scores_the_answers_against_the_exam(answers, points):
    assert score_in_js(items(*answers)) == {"points": points}


def test_the_export_refuses_an_answer_to_a_question_that_is_not_of_the_exam_instead_of_scoring_it_zero():
    result = score_in_js(items(("Otra pregunta", "Verdadero")))
    assert "not a question of this exam" in result["error"] and "student@x.ve" in result["error"]


def test_the_export_refuses_two_questions_with_the_same_statement():
    twin = PAYLOAD["sections"][0]["questions"][0]
    payload = {"key": "k1", "sections": [{"title": "x", "questions": [twin, dict(twin, stem="El  perceptrón es   lineal.")]}]}
    assert "same statement" in score_in_js([], payload)["error"]


def test_the_scoring_cases_use_the_maximum_that_notas_divides_by():
    assert notas.max_points_of(PAYLOAD) == 10    # the perfect case above is the whole exam


# --- gates: discovered from the config and from Code.gs, never from a list somebody remembered to extend ---

def test_gate_every_target_has_its_export_function_in_code_gs():
    code = (APPS_SCRIPT / "Code.gs").read_text(encoding="utf-8")
    targets = publicar.load_config()
    assert targets    # a gate that finds nothing passes green and proves nothing
    for target in targets:
        name = f"exportResponses{publicar.camel(target)}"
        assert re.search(rf"function {name}\(\)\s*\{{\s*return exportResponses_\({publicar.constant_name(target)}\)", code), \
            f"Code.gs has no {name}() calling exportResponses_({publicar.constant_name(target)})"
    declared = set(re.findall(r"function (exportResponses[A-Z]\w*)\(\)", code))
    assert declared == {f"exportResponses{publicar.camel(t)}" for t in targets}, f"{sorted(declared)} do not match the targets"


def test_gate_the_export_emits_every_field_that_notas_reads():
    code = (APPS_SCRIPT / "Code.gs").read_text(encoding="utf-8")
    for field in ("exam_key", "responses", "timestamp", "email", "identification", "score"):
        assert re.search(rf"\b{field}\b\s*:", code), f"exportResponses_ in Code.gs does not emit '{field}'"
    assert "exam.identification" in code    # the titles come from formulario.py, the same ones notas.py reads


def test_gate_the_export_does_not_trust_the_score_google_reports():
    code = (APPS_SCRIPT / "Code.gs").read_text(encoding="utf-8")
    assert not re.search(r"[.]getScore[(]", code), "a call to getScore() came back null in a real exam and a null read as 0 means a failed exam: score the answers instead"
