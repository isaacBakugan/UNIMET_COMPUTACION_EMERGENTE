"""Normalize a Moodle XML question bank export into `banco.json`, the input of the exam builder.

    python parciales/banco.py                      # newest parciales/banco/preguntas-*.xml
    python parciales/banco.py path/to/export.xml   # a specific export

Nothing is dropped silently: every `<question>` of the export ends up in exactly one bucket
(`ok`, `quarantined` with its reasons, or `ignored` for Moodle's own bookkeeping), and the
console report prints the three counts so they can be reconciled against Moodle.

Output (all of `parciales/banco/` is git-ignored, the bank carries the correct answers):
    banco.json            normalized questions, plus the report
    catalogo.csv          one row per usable question (id, category, family, name...) to pick by hand
    imagenes/<id>/<name>  images embedded in the questions (Moodle exports them as base64)
"""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent
BANK_DIR = ROOT / "banco"
BANK_FILE = BANK_DIR / "banco.json"
IMAGES_DIR = BANK_DIR / "imagenes"
CATALOG_FILE = BANK_DIR / "catalogo.csv"

# First path component of the Moodle category -> section of the exam. A category whose first
# component is not listed here is quarantined (`unknown_section`), never guessed.
SECTION_BY_TOP_CATEGORY = {
    "Verdadero o Falso": "true_false",
    "Selección Simple": "simple_choice",
    "Encuentre el intruso": "odd_one_out",
    "Desarrollo (2 c.u.)": "development",
    "Respuesta Corta": "short_answer",
}
# Moodle's default category of the course template: sample questions, not part of the bank.
IGNORED_TOP_CATEGORIES = {"Por defecto en plantilla_1"}
IGNORED_QUESTION_TYPES = {"description"}    # Moodle uses them as category notes

TRUE_FALSE_OPTIONS = {"verdadero", "falso"}
SUBSCRIPTS = str.maketrans("0123456789+-=()ij", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ᵢⱼ")
SUPERSCRIPTS = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
UNIT_PATTERN = re.compile(r"^(?:[A-Za-z]+\.?\s+)?(I{1,3}|IV|V)\s+(\D.*?)(?:\s+\+\d+)?$")
CHAPTER_PATTERN = re.compile(r"^[A-Za-z]+\.?\s+(\d+)(?:\.\d+)*\s*[-–\s]")
NAME_SUFFIX_PATTERN = re.compile(r"\(([TVF])\)\s*$")    # (T)/(V) = true, (F) = false
LATEX_PATTERN = re.compile(r"\\\(|\$\$|\\\[")
TRAILING_PARENTHESIS = re.compile(r"\s*\([^)]*\)\s*$")    # (T) (F) (F1) (desde def) (definición desde nombre)
TRAILING_NUMBER = re.compile(r"\s*[+-]?\d+\s*$")           # "Alan Turing 1", "... 2"


class HtmlToText(HTMLParser):
    """Flatten the HTML of Moodle texts to plain text; Google Forms renders no markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.flags: set[str] = set()
        self._script: list[str] = []    # open <sub>/<sup> -> translation table

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attributes = dict(attrs)
        if tag == "br":
            self.parts.append("\n")
        elif tag in ("p", "div", "ul", "ol", "pre"):
            self.parts.append("\n")
            if "padding-left" in (attributes.get("style") or "") or tag == "pre":
                self.flags.add("layout")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in ("sub", "sup"):
            self._script.append(tag)
        elif tag == "img":
            self.flags.add("image")
        elif tag == "table":
            self.flags.add("table")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("p", "div", "ul", "ol", "pre"):
            self.parts.append("\n")
        elif tag in ("sub", "sup") and self._script:
            self._script.pop()

    def handle_data(self, data: str) -> None:
        if self._script:
            table = SUBSCRIPTS if self._script[-1] == "sub" else SUPERSCRIPTS
            translated = data.translate(table)
            # characters without a Unicode script form (letters) keep a visible marker
            if translated == data and data.strip():
                data = ("_" if self._script[-1] == "sub" else "^") + data
            else:
                data = translated
        self.parts.append(data)


def to_plain_text(raw: str | None) -> tuple[str, set[str]]:
    """Return (plain text, review flags) for a Moodle text field."""
    parser = HtmlToText()
    parser.feed(raw or "")
    parser.close()
    text = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if LATEX_PATTERN.search(raw or ""):
        parser.flags.add("latex")
    return text, parser.flags


@dataclass
class Bank:
    source: str
    ok: list[dict] = field(default_factory=list)
    quarantined: list[dict] = field(default_factory=list)
    ignored: list[dict] = field(default_factory=list)

    def report(self) -> dict:
        return {
            "total": len(self.ok) + len(self.quarantined) + len(self.ignored),
            "ok": len(self.ok),
            "quarantined": len(self.quarantined),
            "ignored": len(self.ignored),
            "ok_by_section": dict(Counter(q["section"] for q in self.ok)),
            "ok_by_section_and_unit": {
                section: dict(Counter(q["unit"] or "(sin unidad)" for q in self.ok if q["section"] == section))
                for section in sorted({q["section"] for q in self.ok})
            },
            "quarantine_reasons": dict(Counter(r for q in self.quarantined for r in q["reasons"])),
            "needs_review": dict(Counter(f for q in self.ok for f in q["review_flags"])),
            "warnings": dict(Counter(w for q in self.ok for w in q["warnings"])),
            "families": len({q["family"] for q in self.ok}),
            "family_sizes": dict(sorted(Counter(Counter(q["family"] for q in self.ok).values()).items())),
            "largest_families": [
                {"family": family, "size": size}
                for family, size in Counter(q["family"] for q in self.ok).most_common(5)
            ],
        }


def family_name(name: str) -> str:
    """Name of the concept a question belongs to: the author marks variants of one question by
    appending a number or a parenthesis to a shared name (`Babbage 1/2/3`, `X (T)` / `X (F)`,
    `X (definición desde nombre)` / `X (nombre desde definición)`). Falls back to the full name."""
    base = name.strip().casefold()
    while True:
        stripped = TRAILING_NUMBER.sub("", TRAILING_PARENTHESIS.sub("", base)).strip()
        if stripped == base or not stripped:
            break
        base = stripped
    return base or name.strip().casefold()


def question_id(stem: str, options: list[dict]) -> str:
    """Stable id from the content: survives renames and option shuffles, changes if the question changes."""
    canonical = json.dumps(
        [stem, sorted((o["text"], o["correct"]) for o in options)], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


def parse_unit_and_chapter(path_parts: list[str]) -> tuple[str | None, int | None]:
    unit = chapter = None
    for part in path_parts:
        match = UNIT_PATTERN.match(part.strip())
        if match and unit is None:
            unit = f"{match.group(1)} {match.group(2).strip()}"
        match = CHAPTER_PATTERN.match(part.strip())
        if match and chapter is None:
            chapter = int(match.group(1))
    return unit, chapter


def normalize_question(element: ElementTree.Element, category: str) -> dict:
    """Turn one `<question type="multichoice">` into the normalized record (reasons go in `reasons`)."""
    path_parts = category.split("/")
    name = (element.findtext("name/text") or "").strip()
    stem, flags = to_plain_text(element.findtext("questiontext/text"))
    options = []
    for answer in element.findall("answer"):
        text, option_flags = to_plain_text(answer.findtext("text"))
        flags |= option_flags
        options.append({"text": text, "correct": float(answer.get("fraction", "0")) > 0})
    files = element.findall(".//file")
    if files:
        flags.add("image")
    unit, chapter = parse_unit_and_chapter(path_parts[1:])
    section = SECTION_BY_TOP_CATEGORY.get(path_parts[0])
    reasons = []
    warnings = []

    correct_count = sum(1 for o in options if o["correct"])
    if section is None:
        reasons.append("unknown_section")
    if not stem:
        reasons.append("empty_stem")
    if len(options) < 2:
        reasons.append("fewer_than_two_options")
    if len({o["text"].casefold() for o in options}) != len(options):
        reasons.append("duplicate_options")
    if correct_count == 0:
        reasons.append("no_correct_answer")
    if correct_count > 1 or element.findtext("single") == "false":
        reasons.append("multiple_correct_answers")    # Forms checkboxes are all-or-nothing: out of scope
    if section == "true_false" and {o["text"].casefold() for o in options} != TRUE_FALSE_OPTIONS:
        reasons.append("true_false_not_binary")

    suffix = NAME_SUFFIX_PATTERN.search(name)
    if suffix and section == "true_false" and "true_false_not_binary" not in reasons and correct_count == 1:
        said_true = suffix.group(1) in ("T", "V")
        really_true = next(o["text"] for o in options if o["correct"]).casefold() == "verdadero"
        if said_true != really_true:
            # only a warning: the answer key (`fraction`) is what Moodle grades with; the (T)/(F) in the
            # name is a human label that is stale in ~5 % of the cases
            warnings.append("name_suffix_contradicts_answer")

    return {
        "id": question_id(stem, options),
        "name": name,
        "section": section,
        "category": category,
        # a nameless question has no sibling to be recognized by: it is its own family
        "family": f"{category}|{family_name(name) or question_id(stem, options)}",
        "unit": unit,
        "chapter": chapter,
        "stem": stem,
        "options": options,
        "shuffle_options": element.findtext("shuffleanswers") != "false",
        "image_files": [f.get("name") for f in files],
        "review_flags": sorted(flags),
        "reasons": reasons,
        "warnings": warnings,
        "_files": [(f.get("name"), f.text) for f in files],
    }


def load_bank(xml_path: Path) -> Bank:
    """Parse the export; raises when it holds no questions (an empty bank must not pass as a green run)."""
    bank = Bank(source=xml_path.name)
    category = ""
    seen_ids: set[str] = set()
    for element in ElementTree.parse(xml_path).getroot().findall("question"):
        question_type = element.get("type")
        if question_type == "category":
            category = (element.findtext("category/text") or "").replace("$course$/top/", "")
            continue
        top = category.split("/")[0]
        if question_type in IGNORED_QUESTION_TYPES or top in IGNORED_TOP_CATEGORIES:
            bank.ignored.append({"name": (element.findtext("name/text") or "").strip(), "category": category,
                                 "type": question_type})
            continue
        if question_type != "multichoice":
            bank.quarantined.append({
                "id": None, "name": (element.findtext("name/text") or "").strip(), "category": category,
                "section": None, "reasons": [f"unsupported_type:{question_type}"], "review_flags": []})
            continue
        record = normalize_question(element, category)
        if record["id"] in seen_ids:
            record["reasons"].append("duplicate_content")
        if record["reasons"]:
            bank.quarantined.append(record)
        else:
            seen_ids.add(record["id"])
            bank.ok.append(record)
    if not (bank.ok or bank.quarantined):
        raise ValueError(f"{xml_path.name}: no questions found; is it a Moodle XML export?")
    return bank


def write_bank(bank: Bank, bank_file: Path = BANK_FILE, images_dir: Path = IMAGES_DIR) -> None:
    """Write `banco.json` and extract the embedded images next to it (ok questions only)."""
    bank_file.parent.mkdir(parents=True, exist_ok=True)
    for question in bank.ok:
        for name, data in question["_files"]:
            target = images_dir / question["id"] / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(data or ""))
    for question in bank.ok + bank.quarantined:
        question.pop("_files", None)
    payload = {"source": bank.source, "report": bank.report(), "questions": bank.ok,
               "quarantined": bank.quarantined, "ignored": bank.ignored}
    bank_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_catalog(bank: Bank, catalog_file: Path = CATALOG_FILE) -> None:
    """One row per usable question, to look up the `id` of a question that must go in an exam by hand."""
    columns = ["id", "section", "unit", "chapter", "category", "family", "name", "stem"]
    with catalog_file.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for q in sorted(bank.ok, key=lambda q: (q["section"], q["category"], q["name"])):
            writer.writerow([q["id"], q["section"], q["unit"] or "", q["chapter"] or "", q["category"],
                             q["family"].split("|", 1)[1], q["name"], q["stem"][:100].replace("\n", " ")])


def main(argv: list[str]) -> int:
    if argv:
        xml_path = Path(argv[0])
    else:
        exports = sorted(BANK_DIR.glob("preguntas-*.xml"))
        if not exports:
            print(f"ERROR: no preguntas-*.xml export found in {BANK_DIR}")
            return 1
        xml_path = exports[-1]
    bank = load_bank(xml_path)
    write_bank(bank)
    write_catalog(bank)
    report = bank.report()
    print(f"Source: {bank.source}")
    print(f"Total {report['total']} = ok {report['ok']} + quarantined {report['quarantined']} + ignored {report['ignored']}")
    print("OK by section:", report["ok_by_section"])
    for section, units in report["ok_by_section_and_unit"].items():
        print(f"  {section}: {units}")
    print("Quarantine reasons:", report["quarantine_reasons"])
    print("Needs review (kept, but check the rendering):", report["needs_review"])
    print("Warnings (kept):", report["warnings"])
    print(f"Families: {report['families']} (size -> count: {report['family_sizes']})")
    for entry in report["largest_families"]:
        print(f"  largest: {entry['size']:>3} x {entry['family']}")
    print(f"Written: {BANK_FILE} and {CATALOG_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
