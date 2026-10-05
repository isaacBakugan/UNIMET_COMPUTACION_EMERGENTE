import csv
import json
from pathlib import Path

import pytest

from lista import BY_TEAM, HEADER, ListEntry, assign_students, normalize, sort_key

CORRECTIONS_DIR = Path(__file__).resolve().parent.parent
ASSIGNMENT_DIRS = sorted(path.parent for path in CORRECTIONS_DIR.glob("tarea-*/tarea.json"))


def read_list(assignment_dir):
    with (assignment_dir / "lista-entrega.csv").open(newline="", encoding="utf-8-sig") as file:
        return [ListEntry(r["last_name"], r["first_name"], r["team"]) for r in csv.DictReader(file)]


# --- Gates discovered from disk (every correcciones/tarea-*/ is subject) ---

@pytest.mark.parametrize("assignment_dir", ASSIGNMENT_DIRS, ids=lambda path: path.name)
def test_gate_delivery_list_is_alphabetical_complete_and_uses_real_team_names(assignment_dir):
    entries = read_list(assignment_dir)
    assert entries, "Empty delivery list: the gate would pass without proving anything"
    assert [sort_key(e) for e in entries] == sorted(sort_key(e) for e in entries), \
        "lista-entrega.csv must be in alphabetical order (last name, then first name)"
    assert len({(sort_key(e), normalize(e.team)) for e in entries}) == len(entries), "Duplicated student"
    state = json.loads((CORRECTIONS_DIR.parent / "trimestre-actual" / "estado.json").read_text(encoding="utf-8-sig"))
    known_teams = {normalize(item["team"]) for item in state}
    unknown = {e.team for e in entries if normalize(e.team) not in known_teams}
    assert not unknown, f"Teams in lista-entrega.csv that are not in estado.json (typo?): {unknown}"


# --- Matching ---

ENTRIES = [ListEntry("Goncalves", "Diego", "Aris"), ListEntry("Girón", "Verónica", "Aris"),
           ListEntry("Arrieta", "Andrés", "Cyberleak"), ListEntry("Rivera", "Luis", "Cyberleak")]


def test_header_names_match_ignoring_accents_case_and_word_order():
    files = [("Aris", "perceptron_2.py", "Veronica GIRON"), ("Aris", "perceptron_3.py", "Goncalves Diego")]
    assigned, warnings = assign_students(files, ENTRIES)
    assert assigned[("Aris", "perceptron_2.py")] == (ENTRIES[1], HEADER)
    assert assigned[("Aris", "perceptron_3.py")] == (ENTRIES[0], HEADER)
    assert [w for w in warnings if "Aris" in w] == []


def test_nameless_files_are_assigned_by_team_in_file_order_and_flagged():
    files = [("Cyberleak", "perceptron_2.py", ""), ("Cyberleak", "perceptron_1.py", "")]
    assigned, warnings = assign_students(files, ENTRIES)
    assert assigned[("Cyberleak", "perceptron_1.py")] == (ENTRIES[2], BY_TEAM)   # Arrieta, alphabetical first
    assert assigned[("Cyberleak", "perceptron_2.py")] == (ENTRIES[3], BY_TEAM)


def test_a_named_file_is_never_stolen_by_the_team_fallback():
    files = [("Aris", "perceptron_1.py", ""), ("Aris", "perceptron_2.py", "Verónica Girón")]
    assigned, _ = assign_students(files, ENTRIES)
    assert assigned[("Aris", "perceptron_2.py")][0].last_name == "Girón"
    assert assigned[("Aris", "perceptron_1.py")] == (ENTRIES[0], BY_TEAM)


def test_unmatched_files_and_entries_are_reported():
    assigned, warnings = assign_students([("Aris", "perceptron_1.py", "Persona Desconocida"),
                                          ("Aris", "perceptron_2.py", "Otra Persona"),
                                          ("Aris", "perceptron_3.py", "Tercera Persona")], ENTRIES[:2])
    assert ("Aris", "perceptron_3.py") not in assigned
    assert any("perceptron_3.py" in w for w in warnings)
    _, warnings = assign_students([], ENTRIES[:1])
    assert any("Goncalves" in w or "Diego" in w for w in warnings)
