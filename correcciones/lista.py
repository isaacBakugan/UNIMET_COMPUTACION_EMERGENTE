"""Official delivery list (alphabetical by last name): match files to students and order the output.

The professor hands in grades in the order of `tarea-N/lista-entrega.csv`. A file is matched
to a list entry by the name in its header (accent/case-insensitive, same team). Files whose
header has no name are assigned by team to the entries still unmatched, in file order, and
flagged `by_team` so they can be fixed by hand later.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

HEADER = "header"
BY_TEAM = "by_team"
UNASSIGNED = "unassigned"


@dataclass(frozen=True)
class ListEntry:
    last_name: str
    first_name: str
    team: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold().strip()


def name_tokens(text: str) -> frozenset[str]:
    return frozenset(normalize(text).replace(".", " ").split())


def sort_key(entry: ListEntry) -> tuple[str, str]:
    return normalize(entry.last_name), normalize(entry.first_name)


def assign_students(files: list[tuple[str, str, str]], entries: list[ListEntry]
                    ) -> tuple[dict[tuple[str, str], tuple[ListEntry, str]], list[str]]:
    """Match (team, file, header_name) triples to list entries.

    Returns ({(team, file): (entry, HEADER | BY_TEAM)}, warnings). Files not matched stay out
    of the dict; entries without a file are reported in the warnings.
    """
    warnings: list[str] = []
    assigned: dict[tuple[str, str], tuple[ListEntry, str]] = {}
    used_entries: set[ListEntry] = set()
    ordered = sorted(entries, key=sort_key)

    for entry in ordered:
        wanted = name_tokens(entry.full_name)
        for team, file, header_name in files:
            if normalize(team) != normalize(entry.team) or (team, file) in assigned or not header_name:
                continue
            tokens = name_tokens(header_name)
            if wanted <= tokens or tokens <= wanted:
                assigned[(team, file)] = (entry, HEADER)
                used_entries.add(entry)
                break

    for team in sorted({team for team, _, _ in files}, key=normalize):
        pending_files = sorted(file for t, file, _ in files if t == team and (t, file) not in assigned)
        pending_entries = [e for e in ordered if normalize(e.team) == normalize(team) and e not in used_entries]
        for file, entry in zip(pending_files, pending_entries):
            assigned[(team, file)] = (entry, BY_TEAM)
            used_entries.add(entry)
        for file in pending_files[len(pending_entries):]:
            warnings.append(f"{team}/{file} no coincide con ninguna entrada de la lista de entrega.")

    for entry in ordered:
        if entry not in used_entries:
            warnings.append(f"{entry.full_name} ({entry.team}) está en la lista de entrega pero no tiene archivo asignado.")
    return assigned, warnings
