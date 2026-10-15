"""Grades of an exam, in base 20 and in the order of the delivery list, from the responses of its Google Form.

    python parciales/notas.py                                   # the `real` exam of publicacion.json
    python parciales/notas.py parcial-1-real                    # any resolved exam, by name
    python parciales/notas.py --responses ruta/respuestas.json  # default: parciales/resultados/<exam>/respuestas.json

Input: the JSON written by `exportResponsesReal()` (Apps Script, see Code.gs) that you download from the Drive folder
`Parciales`. Its `exam_key` must be the key of the resolved exam (else it is another exam, or the same one with other
questions, and the points would mean something else). The `score` of each response is computed by the export itself
(Code.gs, against the correct options of the exam data; a test runs it with node on the same cases as the key); here
it is divided by the maximum of the exam and multiplied by 20 (80 points scaled x4 -> score / 4).

Output in `parciales/resultados/<exam>/` (git-ignored: it carries student grades):
  notas-sheets.csv   Apellido,Nombre,Equipo,Nota,Observación in the order of trimestre-actual/lista-entrega.csv, to paste
                     the `Nota` column in Google Sheets. Someone on the list who did not answer has an empty Nota.
  notas.csv          one row per response, with email, cédula and how it was matched; also the ones not on the list.

A response is matched to the list by the name typed in the Form (accent/case-insensitive, any extra surname or name
is fine, same rule as the corrections). Whoever does not match, or matches two entries, is NOT guessed: it is reported
with its grade so you can type it by hand.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from armar import SPECS_DIR
from banco import BANK_FILE
from formulario import IDENTIFICATION_FIELDS
from publicar import PublishError, build_payload, load_config

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "correcciones"))
from lista import ListEntry, name_tokens, sort_key    # noqa: E402  (the one name-matching rule of the repo)

RESULTS_DIR = ROOT / "resultados"
DELIVERY_LIST_FILE = REPO / "trimestre-actual" / "lista-entrega.csv"
MAXIMUM_GRADE = 20
LAST_NAME_TITLE, FIRST_NAME_TITLE, ID_NUMBER_TITLE = (field["title"] for field in IDENTIFICATION_FIELDS)

MATCHED, NOT_ON_LIST, AMBIGUOUS = "matched", "not_on_list", "ambiguous"


@dataclass
class Submission:
    submitted_at: str
    email: str
    last_name: str
    first_name: str
    id_number: str
    points: Fraction    # scaled points (the Form's integers), as the export scored them
    grade: Fraction = Fraction(0)
    match: str = ""
    entry: ListEntry | None = None
    attempts: int = 1    # responses of the same person; only the earliest counts


def format_grade(grade: Fraction) -> str:
    """15,25 and 17: decimal COMMA, because Sheets in Spanish reads a point as text. The csv writer quotes the cell, so the
    comma does not split the column. Whole numbers carry no decimals."""
    return f"{float(grade):.2f}".rstrip("0").rstrip(".").replace(".", ",")


def to_grade(points: Fraction, max_points: Fraction) -> Fraction:
    return points * MAXIMUM_GRADE / max_points


def max_points_of(payload: dict) -> Fraction:
    return Fraction(sum(q["points"] for section in payload["sections"] for q in section["questions"]))


def load_submissions(data: dict, payload: dict) -> list[Submission]:
    if data.get("exam_key") != payload["key"]:
        raise PublishError(f"the responses are of exam key '{data.get('exam_key')}', but the resolved exam has key "
                           f"'{payload['key']}': another exam, or the same one with other questions. Export again with "
                           "the function of the right target")
    max_points = max_points_of(payload)
    submissions = []
    for response in data["responses"]:
        if response.get("score") is None:
            raise PublishError(f"{response['email']} has no score: the file comes from an older export. "
                               "Push Code.gs again and run exportResponsesReal() once more")
        points = Fraction(str(response["score"]))
        if points > max_points:
            raise PublishError(f"{response['email']} has {points} points, above the maximum of the exam ({max_points}); "
                               "the file does not belong to this exam")
        identification = response["identification"]
        submissions.append(Submission(
            submitted_at=response["timestamp"], email=response["email"],
            last_name=identification.get(LAST_NAME_TITLE, "").strip(), first_name=identification.get(FIRST_NAME_TITLE, "").strip(),
            id_number=identification.get(ID_NUMBER_TITLE, "").strip(), points=points, grade=to_grade(points, max_points)))
    return sorted(submissions, key=lambda s: s.submitted_at)    # the earliest attempt wins


def find_entry(submission: Submission, entries: list[ListEntry]) -> tuple[ListEntry | None, str]:
    tokens = name_tokens(f"{submission.first_name} {submission.last_name}")
    if not tokens:
        return None, NOT_ON_LIST
    candidates = [e for e in entries if name_tokens(e.full_name) <= tokens or tokens <= name_tokens(e.full_name)]
    exact = [e for e in candidates if name_tokens(e.full_name) == tokens]
    if len(exact) == 1:
        return exact[0], MATCHED
    if len(candidates) == 1:
        return candidates[0], MATCHED
    return None, AMBIGUOUS if candidates else NOT_ON_LIST


def assign(submissions: list[Submission], entries: list[ListEntry]) -> dict[ListEntry, Submission]:
    """Match each submission to a list entry; returns the counted submission of every entry that answered."""
    counted: dict[ListEntry, Submission] = {}
    for submission in submissions:
        entry, submission.match = find_entry(submission, entries)
        if entry is None:
            continue
        submission.entry = entry
        if entry in counted:
            counted[entry].attempts += 1
            submission.match = "duplicate"
        else:
            counted[entry] = submission
    return counted


def student_rows(entries: list[ListEntry], counted: dict[ListEntry, Submission]) -> list[dict]:
    rows = []
    for entry in sorted(entries, key=sort_key):
        submission = counted.get(entry)
        if submission is None:
            note = "Sin respuesta en el Form"
        elif submission.attempts > 1:
            note = f"{submission.attempts} respuestas: se tomó la primera, revisar"
        else:
            note = ""
        rows.append({"Apellido": entry.last_name, "Nombre": entry.first_name, "Equipo": entry.team,
                     "Nota": format_grade(submission.grade) if submission else "", "Observación": note})
    return rows


def warnings_of(entries: list[ListEntry], submissions: list[Submission], counted: dict[ListEntry, Submission]) -> list[str]:
    warnings = []
    for submission in submissions:
        who = f"{submission.first_name} {submission.last_name} <{submission.email}> (nota {format_grade(submission.grade)})"
        if submission.match == NOT_ON_LIST:
            warnings.append(f"{who} no está en la lista de entrega: asignar a mano.")
        elif submission.match == AMBIGUOUS:
            warnings.append(f"{who} coincide con más de una entrada de la lista: asignar a mano.")
        elif submission.match == "duplicate":
            warnings.append(f"{who} respondió más de una vez; cuenta solo la primera.")
    for entry in sorted(entries, key=sort_key):
        if entry not in counted:
            warnings.append(f"{entry.full_name} ({entry.team}) no tiene respuesta en el Form.")
    return warnings


def read_list(path: Path) -> list[ListEntry]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [ListEntry(r["last_name"].strip(), r["first_name"].strip(), r["team"].strip()) for r in csv.DictReader(handle)]


def write_outputs(students: list[dict], submissions: list[Submission], max_points: Fraction, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "notas-sheets.csv").open("w", newline="", encoding="utf-8-sig") as handle:    # BOM: Excel/Sheets read the accents
        writer = csv.DictWriter(handle, fieldnames=["Apellido", "Nombre", "Equipo", "Nota", "Observación"])
        writer.writeheader()
        writer.writerows(students)
    with (out_dir / "notas.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["last_name", "first_name", "team", "typed_last_name", "typed_first_name", "id_number", "email",
                         "submitted_at", "points", "max_points", "grade", "match"])
        for s in sorted(submissions, key=lambda s: (sort_key(s.entry) if s.entry else ("￿", ""), s.submitted_at)):
            writer.writerow([s.entry.last_name if s.entry else "", s.entry.first_name if s.entry else "",
                             s.entry.team if s.entry else "", s.last_name, s.first_name, s.id_number, s.email, s.submitted_at,
                             f"{float(s.points):g}", f"{float(max_points):g}", format_grade(s.grade), s.match])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("exam", nargs="?", help="resolved exam name (default: the `real` target of publicacion.json)")
    parser.add_argument("--responses", type=Path, help="default: parciales/resultados/<exam>/respuestas.json")
    parser.add_argument("--list", type=Path, default=DELIVERY_LIST_FILE, dest="delivery_list")
    parser.add_argument("--bank", type=Path, default=BANK_FILE)
    args = parser.parse_args(argv)

    try:
        exam = args.exam or load_config().get("real")
        if not exam:
            raise PublishError("no exam given and publicacion.json has no `real` target")
        responses_file = args.responses or RESULTS_DIR / exam / "respuestas.json"
        if not responses_file.exists():
            raise PublishError(f"{responses_file} not found: run exportResponsesReal() in Apps Script and download the "
                               "respuestas-<key>.json it writes to the Drive folder 'Parciales' to that path")
        if not args.bank.exists():
            raise PublishError(f"{args.bank} not found; run `python parciales/banco.py` first")
        payload = build_payload(exam, json.loads(args.bank.read_text(encoding="utf-8")), SPECS_DIR, args.bank)
        max_points = max_points_of(payload)
        submissions = load_submissions(json.loads(responses_file.read_text(encoding="utf-8")), payload)
        entries = read_list(args.delivery_list)
        counted = assign(submissions, entries)
        students = student_rows(entries, counted)
        out_dir = responses_file.parent if args.responses else RESULTS_DIR / exam
        write_outputs(students, submissions, max_points, out_dir)
    except (PublishError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error!r}" if isinstance(error, KeyError) else f"ERROR: {error}")
        return 1

    grades = [s.grade for s in counted.values()]
    print(f"{exam}: {len(submissions)} responses, {len(counted)}/{len(entries)} students of the list graded (base {MAXIMUM_GRADE}, "
          f"max {float(max_points):g} Google points)")
    if grades:
        print(f"min {format_grade(min(grades))}  mean {format_grade(sum(grades) / len(grades))}  max {format_grade(max(grades))}")
    for warning in warnings_of(entries, submissions, counted):
        print(f"ADVERTENCIA: {warning}")
    print(f"Para Google Sheets: {out_dir / 'notas-sheets.csv'}\nDetalle: {out_dir / 'notas.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
