"""Tests of the exam template resolver (parciales/armar.py) and its gates."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import armar

PARCIALES = Path(__file__).resolve().parent.parent


def make_question(index, section="true_false", category="Verdadero o Falso/VF I Redes/VF 1-Intro", family=None):
    return {"id": f"q{index:03d}", "name": f"Pregunta {index}", "section": section, "category": category,
            "family": family or f"{category}|pregunta {index}",
            "stem": f"enunciado {index}", "review_flags": [],
            "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]}


def make_bank():
    bank = [make_question(i) for i in range(30)]
    # 5 variants of one concept inside the first category
    bank += [make_question(100 + i, family="Verdadero o Falso/VF I Redes/VF 1-Intro|variante") for i in range(5)]
    bank += [make_question(200 + i, "simple_choice", "Selección Simple/SS I Redes") for i in range(10)]
    return bank


def make_template(**overrides):
    template = {
        "title": "Parcial", "mode": "real", "seed": 7,
        "sections": [
            {"title": "VF", "section": "true_false", "points": 0.5,
             "pick": [{"category": "VF 1-Intro", "count": 6}]},
            {"title": "SS", "section": "simple_choice", "points": 1, "pick": [{"category": "SS I Redes", "count": 3}]},
        ],
    }
    template.update(overrides)
    return template


def ids(resolved, title):
    return [q["id"] for s in resolved["sections"] if s["title"] == title for q in s["questions"]]


def test_gate_every_committed_template_example_is_valid():
    """Discovered by disk: a new `*.ejemplo.json` is subject to the contract without registering it."""
    examples = sorted(PARCIALES.rglob("*.ejemplo.json"))
    assert examples, "no *.ejemplo.json found under parciales/: the gate would prove nothing"
    for path in examples:
        errors = armar.validate_template(json.loads(path.read_text(encoding="utf-8")))
        assert errors == [], f"{path.relative_to(PARCIALES)}: {errors}"


@pytest.mark.parametrize("mutate, expected", [
    (lambda t: t.update(mode="exam"), "'mode'"),
    (lambda t: t.update(seed="7"), "'seed'"),
    (lambda t: t.update(extra=1), "unknown key 'extra'"),
    (lambda t: t.update(shuffle_options="yes"), "'shuffle_options'"),
    (lambda t: t["sections"][0].update(section="essay"), "'section'"),
    (lambda t: t["sections"][0].update(points=0), "'points'"),
    (lambda t: t["sections"][0]["pick"].append({"category": "X", "count": 0}), "'count'"),
    (lambda t: t["sections"][0]["pick"].append({"id": "q1", "category": "X", "count": 1}), "must be"),
    (lambda t: t["sections"][0].update(pick=[]), "'pick'"),
])
def test_invalid_templates_are_rejected_with_the_offending_key(mutate, expected):
    template = make_template()
    mutate(template)
    assert any(expected in error for error in armar.validate_template(template))


def test_keys_starting_with_underscore_are_comments():
    template = make_template(_ayuda="texto")
    template["sections"][0]["pick"][0]["_nota"] = "ok"
    assert armar.validate_template(template) == []


def test_the_draw_is_reproducible_and_depends_on_the_seed():
    bank = make_bank()
    first = armar.resolve(make_template(), bank)
    assert first == armar.resolve(make_template(), list(reversed(bank)))    # independent of bank order
    assert ids(first, "VF") != ids(armar.resolve(make_template(seed=8), bank), "VF")


def test_a_variant_is_never_drawn_together_with_its_siblings_nor_twice():
    bank = make_bank()
    by_id = {q["id"]: q for q in bank}
    for seed in range(40):
        picked = [by_id[i] for i in ids(armar.resolve(make_template(seed=seed), bank), "VF")]
        assert len({q["family"] for q in picked}) == len(picked) == 6


def test_asking_for_more_than_the_distinct_questions_available_fails_clearly():
    template = make_template()
    template["sections"][0]["pick"][0]["count"] = 31    # 30 distinct + 1 family of 5 variants = 31 -> ok; 32 -> too many
    armar.resolve(template, make_bank())
    template["sections"][0]["pick"][0]["count"] = 32
    with pytest.raises(armar.TemplateError, match="only 31 distinct"):
        armar.resolve(template, make_bank())


def test_an_unknown_category_suggests_the_close_ones():
    template = make_template()
    template["sections"][0]["pick"][0]["category"] = "VF 1-Intr"
    with pytest.raises(armar.TemplateError, match="VF 1-Intro"):
        armar.resolve(template, make_bank())


def test_changing_one_pick_does_not_reshuffle_the_previous_ones():
    template = make_template()
    template["sections"][0]["pick"].append({"category": "VF 1-Intro", "count": 2})
    before = armar.resolve(template, make_bank())
    template["sections"][0]["pick"][1]["count"] = 5
    after = armar.resolve(template, make_bank())
    assert ids(before, "VF")[:6] == ids(after, "VF")[:6]


def test_a_question_fixed_by_hand_is_kept_in_place_and_the_random_picks_avoid_it_and_its_variants():
    template = make_template()
    template["sections"][0]["pick"] = [{"category": "VF 1-Intro", "count": 5}, {"id": "q100"}]
    for seed in range(40):
        template["seed"] = seed
        resolved = armar.resolve(template, make_bank())
        picked = ids(resolved, "VF")
        assert picked[-1] == "q100"                                      # position preserved
        assert not {f"q{100 + i}" for i in range(1, 5)} & set(picked)   # its variants are never drawn


def test_ids_fixed_by_hand_are_checked():
    bank = make_bank()
    for pick, message in [({"id": "nope"}, "not in the bank"), ({"id": "q200"}, "not 'true_false'")]:
        template = make_template()
        template["sections"][0]["pick"] = [pick]
        with pytest.raises(armar.TemplateError, match=message):
            armar.resolve(template, bank)
    template = make_template()
    template["sections"][0]["pick"] = [{"id": "q001"}, {"id": "q001"}]
    with pytest.raises(armar.TemplateError, match="twice"):
        armar.resolve(template, bank)


def test_questions_flagged_for_review_are_skipped_unless_the_pick_includes_them():
    bank = make_bank()
    for question in bank[:25]:
        question["review_flags"] = ["image"]    # only q025..q029 and the 5 variants stay clean
    clean = {q["id"] for q in bank if not q["review_flags"] and q["section"] == "true_false"}
    template = make_template()
    template["sections"][0]["pick"][0]["count"] = 5
    for seed in range(20):
        template["seed"] = seed
        assert set(ids(armar.resolve(template, bank), "VF")) <= clean
    template["sections"][0]["pick"][0]["include_review"] = True
    template["sections"][0]["pick"][0]["count"] = 20
    assert len(ids(armar.resolve(template, bank), "VF")) == 20    # reachable only with include_review


def test_a_category_where_every_question_needs_review_says_so():
    bank = make_bank()
    for question in bank:
        question["review_flags"] = ["layout"]
    with pytest.raises(armar.TemplateError, match="include_review"):
        armar.resolve(make_template(), bank)


def test_a_question_fixed_by_id_is_allowed_even_if_it_needs_review():
    bank = make_bank()
    bank[0]["review_flags"] = ["image"]
    template = make_template()
    template["sections"][0]["pick"] = [{"id": "q000"}]
    assert ids(armar.resolve(template, bank), "VF") == ["q000"]


def test_the_summary_adds_up_the_points():
    resolved = armar.resolve(make_template(), make_bank())
    assert resolved["summary"] == {"questions": 9, "points": 6.0, "by_section": {"VF": 6, "SS": 3}}


def test_a_resolved_exam_edited_by_hand_is_revalidated_against_the_bank():
    bank = make_bank()
    resolved = armar.resolve(make_template(), bank)
    joined = armar.join_with_bank(resolved, bank)
    assert joined["sections"][0]["questions"][0]["options"]    # full question attached

    broken = copy.deepcopy(resolved)
    broken["sections"][0]["questions"].append({"id": "ghost", "name": "x", "category": ""})
    with pytest.raises(armar.TemplateError, match="not in the bank"):
        armar.join_with_bank(broken, bank)
    broken = copy.deepcopy(resolved)
    broken["sections"][0]["questions"].append(broken["sections"][0]["questions"][0])
    with pytest.raises(armar.TemplateError, match="twice"):
        armar.join_with_bank(broken, bank)


@pytest.mark.parametrize("template_name, expected", [
    ("parcial-1.local.json", "parcial-1.resuelto.local.json"),
    ("parcial-1.json", "parcial-1.resuelto.local.json"),
])
def test_the_resolved_file_always_lands_in_the_ignored_specs_folder(template_name, expected):
    assert armar.output_path_for(Path("cualquier/carpeta") / template_name) == armar.SPECS_DIR / expected
