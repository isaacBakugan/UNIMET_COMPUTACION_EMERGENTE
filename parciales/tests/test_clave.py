"""Tests of the answer key CSV (parciales/clave.py)."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

import clave
import publicar

ROOT = Path(__file__).resolve().parent.parent.parent


def question(index, section, stem, options):
    return {"id": f"q{index:03d}", "name": f"Pregunta {index}", "section": section, "category": "X", "family": f"x|{index}",
            "stem": stem, "shuffle_options": False, "image_files": [], "review_flags": [],
            "options": [{"text": text, "correct": ok} for text, ok in options]}


BANK = {"questions": [
    # stored Falso first on purpose: the Form (and so the key) puts Verdadero first
    question(1, "true_false", "La red tiene capas.", [("Falso", True), ("Verdadero", False)]),
    question(2, "simple_choice", "¿Cuál es la salida?\nConsidere A[2].", [("[1, 2]", False), ("[3, 6]", True), ("[0, 0]", False)]),
    question(3, "development", "Desarrollo con coma, y \"comillas\"", [("uno", True), ("dos", False)]),
]}


def write_resolved(specs_dir, name="examen", ids=("q001", "q002", "q003")):
    sections = [
        {"title": "Verdadero o Falso", "section": "true_false", "points": 0.25, "questions": [{"id": ids[0], "name": "x"}]},
        {"title": "Selección simple", "section": "simple_choice", "points": 0.5, "questions": [{"id": ids[1], "name": "x"}]},
        {"title": "Desarrollo", "section": "development", "points": 2.5, "questions": [{"id": ids[2], "name": "x"}]},
    ]
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / f"{name}.resuelto.local.json").write_text(
        json.dumps({"title": name, "mode": "practice", "sections": sections}), encoding="utf-8")


def payload(tmp_path):
    write_resolved(tmp_path / "specs")
    return publicar.build_payload("examen", BANK, tmp_path / "specs", tmp_path / "banco.json")


def test_one_row_per_question_in_exam_order_with_the_correct_option_and_its_letter(tmp_path):
    rows = clave.answer_key_rows(payload(tmp_path))
    assert [r[0] for r in rows] == ["1", "2", "3"]
    assert [r[1] for r in rows] == ["Verdadero o Falso", "Selección simple", "Desarrollo"]
    assert [r[4] for r in rows] == ["b) Falso", "b) [3, 6]", "a) uno"]    # V/F: Verdadero is `a` in the Form


def test_points_are_the_templates_not_googles_scaled_integers(tmp_path):
    assert [r[2] for r in clave.answer_key_rows(payload(tmp_path))] == ["0.25", "0.5", "2.5"]


def test_the_options_column_lists_every_option_in_the_order_of_the_form(tmp_path):
    rows = clave.answer_key_rows(payload(tmp_path))
    assert rows[0][5] == "a) Verdadero\nb) Falso"
    assert rows[1][5] == "a) [1, 2]\nb) [3, 6]\nc) [0, 0]"


def test_the_csv_round_trips_stems_with_newlines_commas_and_quotes_and_opens_in_excel(tmp_path):
    rows = clave.answer_key_rows(payload(tmp_path))
    path = tmp_path / "out" / "clave.csv"
    clave.write_csv(rows, path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")    # BOM, so the accents survive Excel
    with path.open(encoding="utf-8-sig", newline="") as handle:
        read = list(csv.reader(handle))
    assert read[0] == clave.COLUMNS and read[1:] == rows
    assert read[3][3] == 'Desarrollo con coma, y "comillas"' and read[2][3] == "¿Cuál es la salida?\nConsidere A[2]."


def test_a_question_without_exactly_one_correct_option_is_an_error(tmp_path):
    bad = payload(tmp_path)
    bad["sections"][1]["questions"][0]["options"][0]["correct"] = True
    with pytest.raises(publicar.PublishError, match="2 correct options"):
        clave.answer_key_rows(bad)


def test_main_writes_the_key_of_the_named_exam_and_fails_loudly_when_it_is_not_resolved(tmp_path, monkeypatch, capsys):
    write_resolved(tmp_path / "specs")
    (tmp_path / "banco.json").write_text(json.dumps(BANK), encoding="utf-8")
    monkeypatch.setattr(clave, "SPECS_DIR", tmp_path / "specs")
    monkeypatch.setattr(clave, "RESULTS_DIR", tmp_path / "resultados")
    assert clave.main(["examen", "--bank", str(tmp_path / "banco.json")]) == 0
    assert (tmp_path / "resultados" / "examen" / "clave.csv").exists()
    assert clave.main(["no-existe", "--bank", str(tmp_path / "banco.json")]) == 1
    assert "no-existe.resuelto.local.json not found" in capsys.readouterr().out


def test_gate_the_default_output_folder_is_git_ignored():
    """The key carries the correct answers: a stray `git add .` must never publish it."""
    path = f"parciales/resultados/{publicar.load_config()['practice']}/clave.csv"
    assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0, f"{path} is not git-ignored"
