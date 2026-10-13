"""Turn a resolved exam into `apps-script/ExamData.gs`, the data the Apps Script project builds the Form from.

    python parciales/formulario.py parciales/specs/parcial-1.resuelto.local.json

`ExamData.gs` is just `const EXAM = {...};` (git-ignored: it carries the correct answers). Code.gs
reads it; the contract between the two is enforced by a test (every `EXAM.*`, `section.*`, `q.*`,
`o.*`, `img.*` that Code.gs reads must be emitted here).

Google Forms only accepts INTEGER points per question, so the points of the template are scaled by
the smallest factor that makes them all integers (0.5 -> x2). The factor goes in `points_scale` and in
the Form description; dividing back is the grader's job.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import sys
from fractions import Fraction
from math import lcm
from pathlib import Path

from armar import TemplateError, join_with_bank
from banco import BANK_FILE, IMAGES_DIR

APPS_SCRIPT_DIR = Path(__file__).resolve().parent / "apps-script"
EXAM_DATA_FILE = APPS_SCRIPT_DIR / "ExamData.gs"
MAX_FORM_POINTS = 100    # Google Forms limit per question
# Asked first in a 'real' exam, on a page of their own (shuffling only reorders the items of one page).
# Surname and name are separate so they can be matched against trimestre-actual/lista-entrega.csv.
IDENTIFICATION_FIELDS = [
    {"title": "Apellidos", "help": "", "pattern": ""},
    {"title": "Nombres", "help": "", "pattern": ""},
    {"title": "Cédula de identidad", "help": "Solo números, sin puntos, guiones ni letras.", "pattern": "^[0-9]{6,9}$"},
]


def points_scale(points: list[float]) -> int:
    """Smallest integer factor that turns every points value into an integer."""
    factor = lcm(*(Fraction(str(p)).limit_denominator(100).denominator for p in points))
    scaled = [Fraction(str(p)) * factor for p in points]
    if any(s.denominator != 1 or s > MAX_FORM_POINTS for s in scaled):
        raise TemplateError(f"points {points} cannot be scaled to integers of at most {MAX_FORM_POINTS}")
    return factor


def _options(question: dict) -> list[dict]:
    options = [{"text": o["text"], "correct": o["correct"]} for o in question["options"]]
    if question["section"] == "true_false":    # fixed order, Verdadero first
        options.sort(key=lambda o: o["text"].casefold() != "verdadero")
    return options


def _images(question: dict, images_dir: Path) -> list[dict]:
    images = []
    for name in question["image_files"]:
        data = (images_dir / question["id"] / name).read_bytes()
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        images.append({"name": name, "mime": mime, "data": base64.b64encode(data).decode("ascii")})
    return images


def to_payload(exam: dict, images_dir: Path = IMAGES_DIR) -> dict:
    """`exam` comes from armar.join_with_bank (resolved entries with their full question attached)."""
    scale = points_scale([s["points"] for s in exam["sections"]])
    real = exam["mode"] == "real"
    shuffle_options = exam.get("shuffle_options", False)    # off unless the template opts in
    sections = []
    for section in exam["sections"]:
        questions = []
        for question in section["questions"]:
            if real and question["image_files"]:
                raise TemplateError(
                    f"'{question['name']}' has an image: in a 'real' exam the questions are shuffled and a Form "
                    "image is a separate item, so the image would be detached from its question. "
                    "Use mode 'practice' or drop the question")
            questions.append({
                "id": question["id"], "name": question["name"], "stem": question["stem"],
                "options": _options(question),
                "shuffle_options": shuffle_options and question["section"] != "true_false" and question["shuffle_options"],
                "points": int(Fraction(str(section["points"])) * scale),
                "images": _images(question, images_dir),
            })
        sections.append({"title": section["title"], "section": section["section"], "questions": questions})
    total_questions = sum(len(s["questions"]) for s in sections)
    original_total = sum(Fraction(str(s["points"])) * len(s["questions"]) for s in exam["sections"])
    description = f"{total_questions} preguntas. Puntaje máximo: {int(original_total * scale)}."
    if scale != 1:
        description += f" (Cada punto de Google equivale a 1/{scale} de punto; el total equivale a {float(original_total):g}.)"
    payload = {"title": exam["title"], "mode": exam["mode"], "description": description,
               "points_scale": scale, "identification": IDENTIFICATION_FIELDS if real else [],
               "sections": sections}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload["key"] = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]    # idempotence key of Code.gs
    return payload


def render(payload: dict) -> str:
    return ("// Generated by parciales/formulario.py. Do not edit, do not commit (it carries the correct answers).\n"
            f"const EXAM = {json.dumps(payload, ensure_ascii=False, indent=2)};\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("resolved", type=Path)
    parser.add_argument("--bank", type=Path, default=BANK_FILE)
    parser.add_argument("--output", type=Path, default=EXAM_DATA_FILE)
    args = parser.parse_args(argv)

    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    resolved = json.loads(args.resolved.read_text(encoding="utf-8"))
    try:
        payload = to_payload(join_with_bank(resolved, bank["questions"]), args.bank.parent / "imagenes")
    except TemplateError as error:
        print(f"ERROR: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(payload), encoding="utf-8")
    count = sum(len(s["questions"]) for s in payload["sections"])
    print(f"Written: {args.output} ({count} questions, key {payload['key']}, points x{payload['points_scale']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
