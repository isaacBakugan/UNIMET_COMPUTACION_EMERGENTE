"""Answer key of an exam as a CSV, to go over it with the students after the exam.

    python parciales/clave.py                       # the `practice` exam of publicacion.json
    python parciales/clave.py parcial-1-real        # any resolved exam, by name

Writes `parciales/resultados/<exam>/clave.csv` (git-ignored: it carries the correct answers). The rows come from the
same payload the Form is built from (`formulario.to_payload`), so the options are in the order the students see them and
the key can never differ from what was published. The question numbers follow the resolved exam: they match the Form
when the template says `"shuffle_questions": false`; otherwise the Form shuffles and the number is for the teacher only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from fractions import Fraction
from pathlib import Path

from armar import SPECS_DIR
from banco import BANK_FILE
from publicar import PublishError, build_payload, load_config

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "resultados"
COLUMNS = ["N", "Sección", "Puntos", "Pregunta", "Respuesta correcta", "Opciones"]


def letter(index: int) -> str:
    return chr(ord("a") + index)


def answer_key_rows(payload: dict) -> list[list[str]]:
    """One row per question, in exam order. Points are the template's (0.25, 0.5, 2.5), not Google's integers."""
    rows = []
    for section in payload["sections"]:
        for question in section["questions"]:
            correct = [i for i, option in enumerate(question["options"]) if option["correct"]]
            if len(correct) != 1:
                raise PublishError(f"'{question['name']}' has {len(correct)} correct options; the key needs exactly one")
            points = Fraction(question["points"], payload["points_scale"])
            rows.append([
                str(len(rows) + 1), section["title"], f"{float(points):g}", question["stem"],
                f"{letter(correct[0])}) {question['options'][correct[0]]['text']}",
                "\n".join(f"{letter(i)}) {option['text']}" for i, option in enumerate(question["options"])),
            ])
    return rows


def write_csv(rows: list[list[str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:    # BOM: Excel and Sheets read the accents
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("exam", nargs="?", help="resolved exam name (default: the `practice` target of publicacion.json)")
    parser.add_argument("--bank", type=Path, default=BANK_FILE)
    parser.add_argument("--output", type=Path, help="default: parciales/resultados/<exam>/clave.csv")
    args = parser.parse_args(argv)

    try:
        exam = args.exam or load_config().get("practice")
        if not exam:
            raise PublishError("no exam given and publicacion.json has no `practice` target")
        if not args.bank.exists():
            raise PublishError(f"{args.bank} not found; run `python parciales/banco.py` first")
        bank = json.loads(args.bank.read_text(encoding="utf-8"))
        rows = answer_key_rows(build_payload(exam, bank, SPECS_DIR, args.bank))
        output = args.output or RESULTS_DIR / exam / "clave.csv"
        write_csv(rows, output)
    except (PublishError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1
    print(f"Written: {output} ({len(rows)} questions of '{exam}')")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
