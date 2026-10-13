"""Stage and publish the exams to the Apps Script project: one project, one data file per exam.

    python parciales/publicar.py                    # generates the exam data files (no network)
    python parciales/publicar.py --push             # ... and `clasp push`

`publicacion.json` says which resolved exam goes into which target (`practice`, `real`). Moving to the next exam
is editing those two names and running this again: nothing else changes.

Each target becomes one file of the project, `apps-script/ExamData<Target>.gs` (git-ignored, it carries the correct
answers), holding the constant `EXAM_<TARGET>`; `Code.gs` has the matching `createExam<Target>` function (a gate in
test_publicar.py keeps both sides in step). `apps-script/.clasp.json` (git-ignored, created once with `clasp create`)
links the folder to the Google project, and `clasp push` runs from there.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from armar import SPECS_DIR, TemplateError, join_with_bank
from banco import BANK_FILE
from formulario import render, to_payload

ROOT = Path(__file__).resolve().parent
APPS_SCRIPT_DIR = ROOT / "apps-script"
CONFIG_FILE = ROOT / "publicacion.json"
TARGET_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATA_FILE_PATTERN = "ExamData*.gs"


class PublishError(ValueError):
    """The publication cannot be staged or pushed; the message says what to do."""


def camel(target: str) -> str:
    return "".join(part.capitalize() for part in target.split("-"))


def data_file(target: str) -> str:
    return f"ExamData{camel(target)}.gs"


def constant_name(target: str) -> str:
    return "EXAM_" + target.upper().replace("-", "_")


def function_name(target: str) -> str:
    return f"createExam{camel(target)}"


def load_config(path: Path = CONFIG_FILE) -> dict[str, str]:
    """`{target: resolved exam name}`; validates the shape because a typo here publishes the wrong exam."""
    data = json.loads(path.read_text(encoding="utf-8"))
    targets = {key: value for key, value in data.items() if not key.startswith("_")}
    if not targets:
        raise PublishError(f"{path.name}: no targets declared")
    for target, exam in targets.items():
        if not TARGET_PATTERN.match(target):
            raise PublishError(f"{path.name}: target '{target}' must be lowercase words joined by '-'")
        if not isinstance(exam, str) or not exam.strip():
            raise PublishError(f"{path.name}: target '{target}' must name a resolved exam (e.g. 'parcial-1-real')")
    duplicated = sorted({exam for exam in targets.values() if list(targets.values()).count(exam) > 1})
    if duplicated:
        raise PublishError(f"{path.name}: {duplicated} is assigned to more than one target")
    return targets


def build_payload(exam_name: str, bank: dict, specs_dir: Path = SPECS_DIR, bank_file: Path = BANK_FILE) -> dict:
    resolved_file = specs_dir / f"{exam_name}.resuelto.local.json"
    if not resolved_file.exists():
        raise PublishError(f"{resolved_file.name} not found: resolve it first "
                           f"(python parciales/armar.py parciales/specs/{exam_name}.local.json)")
    resolved = json.loads(resolved_file.read_text(encoding="utf-8"))
    try:
        return to_payload(join_with_bank(resolved, bank["questions"]), bank_file.parent / "imagenes")
    except TemplateError as error:
        raise PublishError(f"{exam_name}: {error}") from error


def stage(payloads: dict[str, dict], apps_script_dir: Path = APPS_SCRIPT_DIR) -> list[Path]:
    """Write the data file of every target and delete the ones of targets that no longer exist.

    A stale `ExamData*.gs` would be pushed with the rest of the folder and still define a global, so the folder must
    hold exactly the current targets."""
    written = []
    for target, payload in payloads.items():
        path = apps_script_dir / data_file(target)
        path.write_text(render(payload, constant_name(target)), encoding="utf-8")
        written.append(path)
    for stale in apps_script_dir.glob(DATA_FILE_PATTERN):
        if stale not in written:
            stale.unlink()
    return written


def push(folder: Path = APPS_SCRIPT_DIR) -> None:
    clasp = shutil.which("clasp")
    if clasp is None:
        raise PublishError("`clasp` is not on the PATH (npm install -g @google/clasp; clasp login)")
    if not (folder / ".clasp.json").exists():
        raise PublishError(
            f"{folder.name}: no .clasp.json, the folder is not linked to a Google project yet. Once:\n"
            f"    Set-Location {folder}\n"
            f"    clasp create --type standalone --title \"Parciales Forms\"")
    # --force: clasp asks before overwriting the manifest, and there is nobody to answer
    result = subprocess.run([clasp, "push", "--force"], cwd=folder)
    if result.returncode != 0:
        raise PublishError(f"clasp push failed (exit {result.returncode}); the Google project still has the previous "
                           "exam data, so createExam* would return the old Form")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--push", action="store_true", help="run `clasp push` after generating the data files")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--bank", type=Path, default=BANK_FILE)
    args = parser.parse_args(argv)

    try:
        targets = load_config(args.config)
        if not args.bank.exists():
            raise PublishError(f"{args.bank} not found; run `python parciales/banco.py` first")
        bank = json.loads(args.bank.read_text(encoding="utf-8"))
        # every payload is built before anything is written: a broken exam must not leave half the project updated
        payloads = {target: build_payload(exam, bank, SPECS_DIR, args.bank) for target, exam in targets.items()}
        for target, path in zip(payloads, stage(payloads, APPS_SCRIPT_DIR)):
            payload = payloads[target]
            count = sum(len(s["questions"]) for s in payload["sections"])
            print(f"{target:<9} {targets[target]} -> {path.name} ({count} questions, key {payload['key']}, "
                  f"points x{payload['points_scale']}); run {function_name(target)}()")
        if args.push:
            push(APPS_SCRIPT_DIR)
    except (PublishError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1
    print("Pushed. Now run the functions above in the Apps Script editor (`clasp open`)." if args.push
          else "Staged only. Add --push to upload.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
