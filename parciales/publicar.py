"""Stage and publish the Apps Script projects of the exams: one project per target, all at once.

    python parciales/publicar.py                    # builds ExamData.gs of every target (no network)
    python parciales/publicar.py --push             # ... and `clasp push` in each one
    python parciales/publicar.py --only parcial     # a single target

`publicacion.json` says which resolved exam goes into which target (`practica`, `parcial`). Moving to the
next exam is editing those two names and running this again: nothing else changes.

Every target is its own Apps Script project, so its own folder `apps-script/<target>/` (git-ignored, it
carries the correct answers): `Code.gs` and `appsscript.json` are copied there from `apps-script/` (the single
source, so the two projects can never drift), `ExamData.gs` is generated, and `.clasp.json` (created once with
`clasp create`) links the folder to its Google project. `clasp push` runs from that folder.
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
SOURCE_FILES = ("Code.gs", "appsscript.json")    # shared by every target, copied on each run
TARGET_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class PublishError(ValueError):
    """The publication cannot be staged or pushed; the message says what to do."""


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


def stage(target: str, payload: dict, apps_script_dir: Path = APPS_SCRIPT_DIR) -> Path:
    """Fill `apps-script/<target>/` so it is ready to `clasp push`; returns the folder."""
    folder = apps_script_dir / target
    folder.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_FILES:
        shutil.copyfile(apps_script_dir / name, folder / name)
    (folder / "ExamData.gs").write_text(render(payload), encoding="utf-8")
    return folder


def push(folder: Path) -> None:
    clasp = shutil.which("clasp")
    if clasp is None:
        raise PublishError("`clasp` is not on the PATH (npm install -g @google/clasp; clasp login)")
    if not (folder / ".clasp.json").exists():
        raise PublishError(
            f"{folder.name}: no .clasp.json, the folder is not linked to a Google project yet. Once:\n"
            f"    Set-Location {folder}\n"
            f"    clasp create --type standalone --title \"Parciales Forms - {folder.name}\"")
    # --force: clasp asks before overwriting the manifest, and there is nobody to answer
    result = subprocess.run([clasp, "push", "--force"], cwd=folder)
    if result.returncode != 0:
        raise PublishError(f"{folder.name}: clasp push failed (exit {result.returncode}); the Google project still has "
                           "the previous ExamData.gs, so createExam would return the old Form")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--push", action="store_true", help="run `clasp push` in each staged target")
    parser.add_argument("--only", metavar="TARGET", help="a single target of publicacion.json")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--bank", type=Path, default=BANK_FILE)
    args = parser.parse_args(argv)

    try:
        targets = load_config(args.config)
        if args.only:
            if args.only not in targets:
                raise PublishError(f"--only {args.only}: not in {args.config.name} (targets: {sorted(targets)})")
            targets = {args.only: targets[args.only]}
        if not args.bank.exists():
            raise PublishError(f"{args.bank} not found; run `python parciales/banco.py` first")
        bank = json.loads(args.bank.read_text(encoding="utf-8"))
        payloads = {target: build_payload(exam, bank, SPECS_DIR, args.bank) for target, exam in targets.items()}
        # every payload is built before anything is written: a broken exam must not leave half the targets updated
        folders = {}
        for target, payload in payloads.items():
            folders[target] = stage(target, payload, APPS_SCRIPT_DIR)
            count = sum(len(s["questions"]) for s in payload["sections"])
            print(f"{target:<10} {targets[target]} -> {folders[target]} ({count} questions, key {payload['key']}, "
                  f"points x{payload['points_scale']})")
        if args.push:
            for target, folder in folders.items():
                print(f"clasp push: {target}")
                push(folder)
    except (PublishError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1
    if args.push:
        print("Pushed. Now run createExam in the Apps Script editor of each project (`clasp open` inside its folder).")
    else:
        print("Staged only. Add --push to upload.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
