"""Resolve an exam template into the exact list of questions of the exam.

    python parciales/armar.py parciales/specs/parcial-1.local.json            # writes parcial-1.resuelto.local.json
    python parciales/armar.py parciales/specs/parcial-1.local.json --force    # overwrite a resolved file that differs

The template says WHAT to ask (sections, points, and for each section a list of picks); the resolved
file says WHICH questions came out. The Google Form is generated from the resolved file, so what the
teacher reviews (and may edit by hand: remove, reorder or replace entries by `id`) is exactly what the
students get. A pick is one of:

    {"category": "VF I Redes Neuronales", "count": 4}   # `count` questions of that category (and its subcategories)
    {"id": "a1b2c3d4e5f6"}                              # this exact question (ids are in banco/catalogo.csv)

A category draw skips the questions flagged for review (image, pseudocode layout, latex: the Form
cannot render them faithfully) unless the pick says `"include_review": true`; a question fixed by
`id` is always allowed.

`category` matches a name or a `/`-separated sub-path of the Moodle category path. The draw is
reproducible (same template + seed + bank = same exam) and each pick has its own stream, so changing
one pick never reshuffles the others. A question is never drawn together with another variant of
itself (same `family`, see banco.py), and never twice. Keys starting with `_` are comments.
"""

from __future__ import annotations

import argparse
import difflib
import json
import random
import sys
from pathlib import Path

from banco import BANK_FILE, SECTION_BY_TOP_CATEGORY

ROOT = Path(__file__).resolve().parent
SPECS_DIR = ROOT / "specs"
MODES = ("practice", "real")
SECTIONS = set(SECTION_BY_TOP_CATEGORY.values())


class TemplateError(ValueError):
    """The template (or the bank it is drawn from) cannot produce the requested exam."""


def _unknown_keys(label: str, data: dict, allowed: set[str]) -> list[str]:
    return [f"{label}: unknown key '{key}'" for key in data if key not in allowed and not key.startswith("_")]


def validate_template(template: dict) -> list[str]:
    """Structural checks that need no bank; returns the list of problems (empty = valid)."""
    errors = _unknown_keys("template", template, {"title", "mode", "seed", "sections"})
    if not isinstance(template.get("title"), str) or not template["title"].strip():
        errors.append("template: 'title' must be a non-empty string")
    if template.get("mode") not in MODES:
        errors.append(f"template: 'mode' must be one of {MODES}")
    if not isinstance(template.get("seed"), int) or isinstance(template.get("seed"), bool):
        errors.append("template: 'seed' must be an integer")
    sections = template.get("sections")
    if not isinstance(sections, list) or not sections:
        return errors + ["template: 'sections' must be a non-empty list"]
    for s_index, section in enumerate(sections):
        label = f"sections[{s_index}]"
        errors += _unknown_keys(label, section, {"title", "section", "points", "pick"})
        if not isinstance(section.get("title"), str) or not section["title"].strip():
            errors.append(f"{label}: 'title' must be a non-empty string")
        if section.get("section") not in SECTIONS:
            errors.append(f"{label}: 'section' must be one of {sorted(SECTIONS)}")
        points = section.get("points")
        if not isinstance(points, (int, float)) or isinstance(points, bool) or points <= 0:
            errors.append(f"{label}: 'points' must be a number > 0 (points per question)")
        picks = section.get("pick")
        if not isinstance(picks, list) or not picks:
            errors.append(f"{label}: 'pick' must be a non-empty list")
            continue
        for p_index, pick in enumerate(picks):
            pick_label = f"{label}.pick[{p_index}]"
            keys = {key for key in pick if not key.startswith("_")}
            if keys == {"id"}:
                if not isinstance(pick["id"], str) or not pick["id"]:
                    errors.append(f"{pick_label}: 'id' must be a non-empty string")
            elif keys in ({"category", "count"}, {"category", "count", "include_review"}):
                if not isinstance(pick["category"], str) or not pick["category"].strip():
                    errors.append(f"{pick_label}: 'category' must be a non-empty string")
                if not isinstance(pick["count"], int) or isinstance(pick["count"], bool) or pick["count"] < 1:
                    errors.append(f"{pick_label}: 'count' must be an integer >= 1")
                if "include_review" in keys and not isinstance(pick["include_review"], bool):
                    errors.append(f"{pick_label}: 'include_review' must be true or false")
            else:
                errors.append(f"{pick_label}: must be {{'id'}} or {{'category', 'count'[, 'include_review']}}, "
                              f"got {sorted(keys)}")
    return errors


def _category_matches(question: dict, target: str) -> bool:
    """True when the target (a name or a `/` sub-path) is a contiguous run of the category path."""
    path = [part.strip().casefold() for part in question["category"].split("/")]
    wanted = [part.strip().casefold() for part in target.split("/")]
    return any(path[i:i + len(wanted)] == wanted for i in range(len(path) - len(wanted) + 1))


def _suggest_categories(questions: list[dict], target: str) -> str:
    names = sorted({part.strip() for q in questions for part in q["category"].split("/")})
    close = difflib.get_close_matches(target, names, n=3, cutoff=0.5)
    return f" Did you mean: {close}?" if close else ""


def resolve(template: dict, bank: list[dict], template_name: str = "", bank_source: str = "") -> dict:
    """Draw the exam. `bank` is the list of usable questions of banco.json."""
    errors = validate_template(template)
    if errors:
        raise TemplateError("invalid template:\n  " + "\n  ".join(errors))
    by_id = {q["id"]: q for q in bank}
    used_ids: set[str] = set()
    used_families: set[str] = set()
    warnings: list[str] = []

    # pass 1: the questions fixed by hand, so the random picks (whatever their position) avoid them
    for s_index, section in enumerate(template["sections"]):
        for pick in section["pick"]:
            if "id" not in pick:
                continue
            question = by_id.get(pick["id"])
            where = f"section '{section['title']}'"
            if question is None:
                raise TemplateError(f"{where}: id '{pick['id']}' is not in the bank (re-run banco.py? is it quarantined?)")
            if question["section"] != section["section"]:
                raise TemplateError(f"{where}: id '{pick['id']}' ({question['name']}) is a "
                                    f"'{question['section']}' question, not '{section['section']}'")
            if pick["id"] in used_ids:
                raise TemplateError(f"{where}: id '{pick['id']}' ({question['name']}) is picked twice")
            if question["family"] in used_families:
                warnings.append(f"{where}: '{question['name']}' is a variant of another question fixed by hand")
            used_ids.add(pick["id"])
            used_families.add(question["family"])

    # pass 2: build every section in declared order
    sections_out = []
    for s_index, section in enumerate(template["sections"]):
        chosen: list[dict] = []
        for p_index, pick in enumerate(section["pick"]):
            if "id" in pick:
                chosen.append(by_id[pick["id"]])
                continue
            pool = [q for q in bank if q["section"] == section["section"] and _category_matches(q, pick["category"])]
            if not pool:
                raise TemplateError(f"section '{section['title']}': no '{section['section']}' question in category "
                                    f"'{pick['category']}'." + _suggest_categories(bank, pick["category"]))
            if not pick.get("include_review", False):
                reviewable = [q for q in pool if not q["review_flags"]]
                if not reviewable:
                    raise TemplateError(f"section '{section['title']}': all {len(pool)} questions of "
                                        f"'{pick['category']}' need review (image, layout or latex); "
                                        "add \"include_review\": true to the pick to draw them anyway")
                pool = reviewable
            available = [q for q in pool if q["id"] not in used_ids and q["family"] not in used_families]
            families = sorted({q["family"] for q in available})
            if pick["count"] > len(families):
                raise TemplateError(f"section '{section['title']}': {pick['count']} questions requested from "
                                    f"'{pick['category']}' but only {len(families)} distinct ones are available "
                                    f"({len(pool)} in the category, the rest are variants or already used)")
            rng = random.Random(f"{template['seed']}:{s_index}:{p_index}")    # own stream per pick
            for family in rng.sample(families, pick["count"]):
                members = sorted((q for q in available if q["family"] == family), key=lambda q: q["id"])
                question = rng.choice(members)
                used_ids.add(question["id"])
                used_families.add(family)
                chosen.append(question)
        sections_out.append({
            "title": section["title"], "section": section["section"], "points": section["points"],
            "questions": [{"id": q["id"], "name": q["name"], "category": q["category"]} for q in chosen],
        })

    total_questions = sum(len(s["questions"]) for s in sections_out)
    return {
        "title": template["title"], "mode": template["mode"], "seed": template["seed"],
        "template": template_name, "bank": bank_source, "sections": sections_out,
        "summary": {
            "questions": total_questions,
            "points": round(sum(s["points"] * len(s["questions"]) for s in sections_out), 4),
            "by_section": {s["title"]: len(s["questions"]) for s in sections_out},
        },
        "warnings": warnings,
    }


def join_with_bank(resolved: dict, bank: list[dict]) -> dict:
    """Attach the full question (stem, options, correct answer) to every entry of a resolved exam.

    Used by the Form builder. Validates the resolved file, which may have been edited by hand."""
    by_id = {q["id"]: q for q in bank}
    seen: set[str] = set()
    sections = []
    for section in resolved["sections"]:
        questions = []
        for entry in section["questions"]:
            question = by_id.get(entry["id"])
            if question is None:
                raise TemplateError(f"resolved exam: id '{entry['id']}' ({entry.get('name', '?')}) is not in the bank")
            if question["section"] != section["section"]:
                raise TemplateError(f"resolved exam: '{question['name']}' is a '{question['section']}' question "
                                    f"inside the '{section['section']}' section")
            if entry["id"] in seen:
                raise TemplateError(f"resolved exam: id '{entry['id']}' ({question['name']}) appears twice")
            seen.add(entry["id"])
            questions.append(question)
        sections.append({**section, "questions": questions})
    return {**resolved, "sections": sections}


def output_path_for(template_path: Path) -> Path:
    stem = template_path.name
    for suffix in (".local.json", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return SPECS_DIR / f"{stem}.resuelto.local.json"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("template", type=Path)
    parser.add_argument("--bank", type=Path, default=BANK_FILE)
    parser.add_argument("--force", action="store_true", help="overwrite a resolved file that differs")
    args = parser.parse_args(argv)

    if not args.bank.exists():
        print(f"ERROR: {args.bank} not found; run `python parciales/banco.py` first")
        return 1
    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    template = json.loads(args.template.read_text(encoding="utf-8"))
    try:
        resolved = resolve(template, bank["questions"], args.template.name, bank["source"])
    except TemplateError as error:
        print(f"ERROR: {error}")
        return 1

    output = output_path_for(args.template)
    text = json.dumps(resolved, ensure_ascii=False, indent=2) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") == text:
        print(f"Unchanged: {output}")
    elif output.exists() and not args.force:
        print(f"ERROR: {output} exists and differs (edited by hand, or the template/bank changed). "
              "Review it, or re-run with --force to overwrite it.")
        return 1
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"Written: {output}")
    print(f"{resolved['summary']['questions']} questions, {resolved['summary']['points']} points: "
          f"{resolved['summary']['by_section']}")
    for warning in resolved["warnings"]:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
