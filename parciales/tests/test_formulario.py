"""Tests of the Form payload builder (parciales/formulario.py) and of its contract with Code.gs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import armar
import formulario

APPS_SCRIPT = Path(__file__).resolve().parent.parent / "apps-script"


def make_question(index, section="simple_choice", image_files=(), options=None):
    return {"id": f"q{index:03d}", "name": f"Pregunta {index}", "section": section, "category": "X", "family": f"x|{index}",
            "stem": f"enunciado {index}", "shuffle_options": True, "image_files": list(image_files), "review_flags": [],
            "options": options or [{"text": "a", "correct": False}, {"text": "b", "correct": True}]}


def make_exam(mode="practice", points=(1, 1), questions=None):
    questions = questions or [make_question(1, "true_false", options=[{"text": "Falso", "correct": True},
                                                                         {"text": "Verdadero", "correct": False}]),
                              make_question(2)]
    return {"title": "Parcial", "mode": mode, "sections": [
        {"title": "VF", "section": "true_false", "points": points[0], "questions": questions[:1]},
        {"title": "SS", "section": "simple_choice", "points": points[1], "questions": questions[1:]},
    ]}


@pytest.mark.parametrize("points, factor", [([1, 2], 1), ([0.5, 1], 2), ([0.25], 4), ([0.5, 0.25], 4)])
def test_points_are_scaled_to_the_smallest_integer_factor(points, factor):
    assert formulario.points_scale(points) == factor


def test_points_that_cannot_fit_google_forms_are_rejected():
    with pytest.raises(armar.TemplateError):
        formulario.points_scale([150])


def test_true_false_keeps_a_fixed_order_and_is_never_option_shuffled(tmp_path):
    payload = formulario.to_payload({**make_exam(), "shuffle_options": True}, tmp_path)
    true_false, simple = (s["questions"][0] for s in payload["sections"])
    assert [o["text"] for o in true_false["options"]] == ["Verdadero", "Falso"]
    assert true_false["shuffle_options"] is False and simple["shuffle_options"] is True


def test_options_are_not_shuffled_unless_the_template_opts_in(tmp_path):
    for exam in (make_exam(), {**make_exam(), "shuffle_options": False}):
        payload = formulario.to_payload(exam, tmp_path)
        assert not any(q["shuffle_options"] for s in payload["sections"] for q in s["questions"])


def test_scaled_points_are_integers_and_the_description_explains_the_scale(tmp_path):
    payload = formulario.to_payload(make_exam(points=(0.5, 1)), tmp_path)
    assert [q["points"] for s in payload["sections"] for q in s["questions"]] == [1, 2]
    assert payload["points_scale"] == 2 and "1/2" in payload["description"]


def test_a_real_exam_rejects_images_but_a_practice_exam_embeds_them(tmp_path):
    (tmp_path / "q002").mkdir()
    (tmp_path / "q002" / "fig.png").write_bytes(b"png-bytes")
    with_image = [make_question(1, "true_false"), make_question(2, image_files=["fig.png"])]
    with pytest.raises(armar.TemplateError, match="image"):
        formulario.to_payload(make_exam("real", questions=with_image), tmp_path)
    payload = formulario.to_payload(make_exam("practice", questions=with_image), tmp_path)
    image = payload["sections"][1]["questions"][0]["images"][0]
    assert image["mime"] == "image/png" and image["name"] == "fig.png"


def test_only_a_real_exam_asks_for_surname_name_and_id_number(tmp_path):
    assert formulario.to_payload(make_exam("practice"), tmp_path)["identification"] == []
    fields = formulario.to_payload(make_exam("real"), tmp_path)["identification"]
    assert [f["title"] for f in fields] == ["Apellidos", "Nombres", "Cédula de identidad"]
    assert all(f["title"] for f in fields)


@pytest.mark.parametrize("value, valid", [("12345678", True), ("987654", True), ("V12345678", False),
                                          ("12.345.678", False), ("12345678 ", False), ("123", False), ("", False)])
def test_the_id_number_accepts_digits_only(value, valid):
    pattern = formulario.IDENTIFICATION_FIELDS[-1]["pattern"]
    assert (re.fullmatch(pattern, value) is not None) is valid


def test_the_idempotence_key_follows_the_content(tmp_path):
    base = formulario.to_payload(make_exam(), tmp_path)
    assert base["key"] == formulario.to_payload(make_exam(), tmp_path)["key"]
    assert base["key"] != formulario.to_payload(make_exam(mode="real"), tmp_path)["key"]


def test_the_generated_file_is_a_js_constant_that_round_trips(tmp_path):
    payload = formulario.to_payload(make_exam(), tmp_path)
    text = formulario.render(payload)
    body = text.split("const EXAM = ", 1)[1].rsplit(";", 1)[0]
    assert json.loads(body) == payload


def test_gate_code_gs_only_reads_fields_that_formulario_emits(tmp_path):
    """Contract Python <-> Apps Script: renaming a field on one side must fail here, not in the Form."""
    (tmp_path / "q002").mkdir()
    (tmp_path / "q002" / "fig.png").write_bytes(b"x")
    exam = make_exam(questions=[make_question(1, "true_false"), make_question(2, image_files=["fig.png"])])
    payload = formulario.to_payload(exam, tmp_path)
    real_payload = formulario.to_payload(make_exam("real"), tmp_path)
    emitted = {
        "exam": set(payload),
        "field": set(real_payload["identification"][0]),
        "section": set(payload["sections"][0]),
        "q": set(payload["sections"][1]["questions"][0]),
        "o": set(payload["sections"][1]["questions"][0]["options"][0]),
        "img": set(payload["sections"][1]["questions"][0]["images"][0]),
    }
    code = (APPS_SCRIPT / "Code.gs").read_text(encoding="utf-8")
    for variable, fields in emitted.items():
        read = set(re.findall(rf"\b{variable}\.(\w+)", code))
        assert read, f"Code.gs reads no `{variable}.*` field: the gate would prove nothing"
        assert read <= fields, f"Code.gs reads `{variable}.{sorted(read - fields)}` which formulario.py does not emit"


def test_gate_the_forms_advanced_service_is_declared_when_code_gs_uses_it():
    manifest = json.loads((APPS_SCRIPT / "appsscript.json").read_text(encoding="utf-8"))
    code = (APPS_SCRIPT / "Code.gs").read_text(encoding="utf-8")
    declared = {s["userSymbol"] for s in manifest.get("dependencies", {}).get("enabledAdvancedServices", [])}
    assert ("Forms.Forms." not in code) or "Forms" in declared, "Code.gs calls Forms.Forms but appsscript.json does not enable it"
