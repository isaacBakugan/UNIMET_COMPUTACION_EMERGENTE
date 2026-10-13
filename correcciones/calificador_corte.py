"""Grade a `corte-preguntas-N` deliverable of every team with one command.

    python correcciones/calificador_corte.py            # grade everything (corte-preguntas-1)
    python correcciones/calificador_corte.py --corte corte-preguntas-2   # another corte
    python correcciones/calificador_corte.py --update   # fetch the team repos from GitHub first
    python correcciones/calificador_corte.py --team G1  # only one team

The deliverable (`preguntas.json`) is per team, but lateness is INDIVIDUAL:
  * every student gets the grade of the team's file at the last commit before the cutoff, no penalty;
  * a student who pushed commits after the cutoff (identified by commit author email, see
    `<corte>/autores.csv`) gets max(cutoff version, latest version - late penalty).
The authoritative unit tests of the corte (see the criteria of its `corte.json`) are run for each version. Writes `notas.csv` (per team), `notas-sheets.csv` (per student, alphabetical, ready for Google
Sheets) and `informe.md`.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from clones import sync_clone
from corte import CorteConfig, CorteResult, final_grade, load_config, run_tests, score
from entregas import (commit_at_cutoff, commit_date, commits_after_cutoff_by_author, export_assignment, git,
                      remote_ref, to_utc_iso)
from lista import ListEntry, normalize, sort_key

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORTE = "corte-preguntas-1"
STATE_FILE = ROOT / "trimestre-actual" / "estado.json"
DELIVERY_LIST_FILE = ROOT / "trimestre-actual" / "lista-entrega.csv"


@dataclass
class TeamRow:
    team: str
    repo: str
    url: str
    cutoff_commit: str = ""
    cutoff_date: str = ""
    late_commits: list[tuple[str, str]] = field(default_factory=list)   # (date, author email), newest first
    cutoff_result: CorteResult | None = None
    latest_result: CorteResult | None = None    # only when there are commits after the cutoff
    notes: list[str] = field(default_factory=list)
    error: str = ""

    def cutoff_grade(self, config: CorteConfig) -> int | None:
        return None if self.cutoff_result is None else final_grade(config, self.cutoff_result.points)

    def late_version_grade(self, config: CorteConfig) -> int | None:
        if self.latest_result is None:
            return None
        return final_grade(config, self.latest_result.points, config.late_penalty_points)

    @property
    def late_emails(self) -> set[str]:
        return {email for _, email in self.late_commits}


def student_grade(row: TeamRow, config: CorteConfig, is_late: bool) -> tuple[int | None, bool]:
    """Student grade and whether the late penalty applied.

    A late team keeps the better of (cutoff version) and (latest version minus penalty), so a late
    commit never hurts the team.
    """
    base = row.cutoff_grade(config)
    if base is None:
        return None, False
    late = row.late_version_grade(config)
    if is_late and late is not None and late > base:
        return late, True
    return base, False


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def load_authors(path: Path) -> dict[str, tuple[str, str]]:
    """author email (lowercase) -> (last name, first name). Duplicated emails are an error."""
    authors: dict[str, tuple[str, str]] = {}
    for row in read_csv(path):
        email = row["author_email"].strip().lower()
        if email in authors:
            raise ValueError(f"Duplicated author email in {path.name}: {email}")
        authors[email] = (row["last_name"].strip(), row["first_name"].strip())
    return authors


def load_active_teams(config: CorteConfig) -> tuple[str, list[dict]]:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
    teams = [item for item in state if item.get("status") == "active" and item["team"] not in config.excluded_teams]
    if not teams:
        raise ValueError(f"No active teams to grade in {STATE_FILE}")
    terms = {item["term"] for item in teams}
    if len(terms) != 1:
        raise ValueError(f"Expected a single term in {STATE_FILE}, found {sorted(terms)}")
    return terms.pop(), teams


def grade_commit(repo: Path, config: CorteConfig, sha: str | None, work_dir: Path, team: str) -> CorteResult:
    """Export the deliverable at `sha` (None = no commit) and run the authoritative tests on it."""
    questions_file = work_dir / "sources" / repo.name / "missing" / config.deliverable
    if sha:
        exported = export_assignment(repo, sha, work_dir / "sources" / repo.name / sha[:10], config.folder)
        questions_file = exported / config.deliverable
    return score(config, run_tests(config.test_file, questions_file.resolve(), work_dir / "evidence" / team / (sha or "none")[:10]))


def evaluate_team(item: dict, config: CorteConfig, clones: Path, work_dir: Path, update: bool) -> TeamRow:
    """Run the tests on the cutoff version and, when there are later commits, on the latest version."""
    row = TeamRow(team=item["team"], repo=item["repo"], url=item["url"])
    repo = clones / item["repo"]
    try:
        if update:
            sync_clone(item["url"], repo)
        if not (repo / ".git").exists():
            raise RuntimeError(f"No existe el clon local {repo}; ejecutar con --update.")
        ref = remote_ref(repo)
        row.late_commits = commits_after_cutoff_by_author(repo, config.cutoff, ref, config.folder)
        cutoff_sha = commit_at_cutoff(repo, config.cutoff, ref)
        if cutoff_sha:
            row.cutoff_commit, row.cutoff_date = cutoff_sha, commit_date(repo, cutoff_sha)
        else:
            row.notes.append("Sin commits hasta el cierre.")
        row.cutoff_result = grade_commit(repo, config, cutoff_sha, work_dir, item["team"])
        if row.late_commits:
            row.latest_result = grade_commit(repo, config, git(repo, "rev-parse", ref), work_dir, item["team"])
        if row.cutoff_result.tests_passed == 0:
            row.notes.append("Ninguna prueba pasó al cierre: el archivo está vacío, ilegible o conserva el texto de la plantilla.")
    except (RuntimeError, OSError, ValueError) as exc:
        row.error = str(exc)
    return row


def load_delivery_list(path: Path) -> list[ListEntry]:
    return [ListEntry(r["last_name"].strip(), r["first_name"].strip(), r["team"].strip()) for r in read_csv(path)]


def student_rows(entries: list[ListEntry], rows: list[TeamRow], config: CorteConfig,
                 authors: dict[str, tuple[str, str]], warnings: list[str]) -> list[dict]:
    """One row per student in alphabetical delivery order, with the team late rule applied."""
    by_team = {normalize(row.team): row for row in rows}
    emails_of: dict[tuple[str, str], set[str]] = {}
    for email, (last, first) in authors.items():
        emails_of.setdefault((normalize(last), normalize(first)), set()).add(email)
    for row in rows:
        for email in sorted(row.late_emails - set(authors)):
            warnings.append(f"{row.team}: hay commits tardíos de {email}, que no está en autores.csv.")
    result = []
    for entry in sorted(entries, key=sort_key):
        team_row = by_team.get(normalize(entry.team))
        if team_row is None:
            continue   # team not graded in this run (--team filter)
        is_late = bool(team_row.late_commits)
        grade, penalized = student_grade(team_row, config, is_late)
        observations = []
        if grade is None:
            observations.append("Sin resultado: " + team_row.error)
        elif penalized:
            observations.append(f"Entrega tardía: -{config.late_penalty_points} puntos")
        elif is_late:
            observations.append("Commits tardíos sin efecto: la versión al cierre es igual o mejor")
        result.append({"Apellido": entry.last_name, "Nombre": entry.first_name, "Equipo": entry.team,
                       "Nota": "" if grade is None else grade, "Observación": "; ".join(observations)})
    listed = {normalize(entry.team) for entry in entries}
    for row in rows:
        if normalize(row.team) not in listed:
            warnings.append(f"El equipo {row.team} no tiene estudiantes en lista-entrega.csv.")
    return result


def team_cell(row: TeamRow) -> str:
    return "sí" if not row.late_commits else f"{len(row.late_commits)} tardíos"


def write_outputs(rows: list[TeamRow], students: list[dict], config: CorteConfig, out_dir: Path, term: str,
                  warnings: list[str], preliminary: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [criterion.key for criterion in config.criteria]
    with (out_dir / "notas.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["team", "repo", "cutoff_commit", "cutoff_date", "late_commits", "late_authors",
                         *keys, "tests_passed", "tests_total", "points", "cutoff_grade", "late_version_grade", "error"])
        for row in rows:
            result = row.cutoff_result
            scores = {s.key: s for s in result.scores} if result else {}
            writer.writerow([row.team, row.repo, row.cutoff_commit, row.cutoff_date, len(row.late_commits),
                             "; ".join(sorted(row.late_emails)),
                             *[f"{float(scores[k].points):.2f}" if k in scores else "" for k in keys],
                             result.tests_passed if result else "", result.tests_total if result else "",
                             f"{float(result.points):.2f}" if result else "",
                             row.cutoff_grade(config) if result else "",
                             row.late_version_grade(config) if row.latest_result else "", row.error])
    with (out_dir / "notas-sheets.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["Apellido", "Nombre", "Equipo", "Nota", "Observación"])
        writer.writeheader()
        writer.writerows(students)

    lines = [f"# Corrección automática: {config.name} ({term})", ""]
    if preliminary:
        lines += ["> **PRELIMINAR:** el cierre aún no ha ocurrido; se evaluó el último commit actual de cada equipo.", ""]
    lines += [f"Cierre: {config.cutoff}. El entregable (`{config.deliverable}`) es del equipo, y la entrega tardía es "
              f"**grupal**: todo el equipo recibe la mejor nota entre la versión al cierre y la versión final con "
              f"{config.late_penalty_points} puntos menos. Las notas salen de ejecutar las mismas pruebas unitarias que corren los "
              "estudiantes. " + f"La nota máxima es {config.maximum_grade}; puntos por criterio: "
              + ", ".join(f"{c.key} {c.points}" for c in config.criteria) + ", proporcionales a las pruebas que pasan.", "",
              "| Equipo | Commits tardíos | " + " | ".join(c.key for c in config.criteria) + " | Pruebas | Nota al cierre | Versión final (-2) |",
              "|---|---|" + "---:|" * len(config.criteria) + "---:|---:|---:|"]
    for row in rows:
        if row.cutoff_result is None:
            lines.append(f"| {row.team} | {team_cell(row)} | " + " | ".join("-" for _ in config.criteria) + " | - | **sin resultado** | - |")
            continue
        scores = {s.key: s for s in row.cutoff_result.scores}
        final = row.late_version_grade(config)
        lines.append(f"| {row.team} | {team_cell(row)} | "
                     + " | ".join(f"{float(scores[c.key].points):.1f}/{c.points}" for c in config.criteria)
                     + f" | {row.cutoff_result.tests_passed}/{row.cutoff_result.tests_total} | **{row.cutoff_grade(config)}** | {final if final is not None else '-'} |")
    lines += ["", "## Notas por estudiante (orden alfabético)", "", "| # | Apellido, nombre | Equipo | Nota | Observación |", "|---:|---|---|---:|---|"]
    for number, student in enumerate(students, 1):
        lines.append(f"| {number} | {student['Apellido']}, {student['Nombre']} | {student['Equipo']} | **{student['Nota']}** | {student['Observación']} |")
    if warnings:
        lines += ["", "## Advertencias", ""] + [f"- {text}" for text in warnings]
    lines += ["", "## Detalle por equipo (versión al cierre)", ""]
    for row in rows:
        grade = row.cutoff_grade(config)
        lines += [f"### {row.team} — {grade if grade is not None else 'sin resultado'}/{config.maximum_grade}", "",
                  f"Commit evaluado al cierre: `{row.cutoff_commit or 'ninguno'}` ({row.cutoff_date or 'sin fecha'}). "
                  + ("Sin commits posteriores al cierre." if not row.late_commits else
                     f"Commits posteriores al cierre: {len(row.late_commits)} (último: {row.late_commits[0][0]}, de {row.late_commits[0][1]}). "
                     f"La versión final obtiene {row.late_version_grade(config)} con el descuento."), ""]
        if row.error:
            lines += [f"**Error:** {row.error}", ""]
        if row.cutoff_result:
            for criterion in config.criteria:
                criterion_score = next(s for s in row.cutoff_result.scores if s.key == criterion.key)
                lines.append(f"- **{criterion.description}: {float(criterion_score.points):.1f}/{criterion.points}** "
                             f"({criterion_score.passed}/{criterion_score.total} pruebas)")
                for name in criterion.tests:
                    for outcome in row.cutoff_result.outcomes.get(name, []):
                        if not outcome.passed:
                            lines.append(f"  - ✗ `{name}`: {outcome.message or 'falló'}")
        lines += [f"> {note}" for note in row.notes] + [""]
    (out_dir / "informe.md").write_text("\n".join(lines), encoding="utf-8")


def print_summary(rows: list[TeamRow], students: list[dict], config: CorteConfig, out_dir: Path, preliminary: bool) -> None:
    if preliminary:
        print("\n*** PRELIMINAR: el cierre aún no ha ocurrido; se evalúa el último commit actual ***")
    print(f"\n{'Equipo':<12} {'Tardíos':<10} " + " ".join(f"{c.key:>{max(6, len(c.key))}}" for c in config.criteria) + "  Pruebas  Cierre  Final(-2)")
    for row in rows:
        if row.cutoff_result is None:
            print(f"{row.team:<12} {team_cell(row):<10} ERROR: {row.error}")
            continue
        scores = {s.key: s for s in row.cutoff_result.scores}
        final = row.late_version_grade(config)
        print(f"{row.team:<12} {team_cell(row):<10} " + " ".join(f"{float(scores[c.key].points):>{max(6, len(c.key))}.1f}" for c in config.criteria)
              + f"  {row.cutoff_result.tests_passed:>3}/{row.cutoff_result.tests_total:<3}  {row.cutoff_grade(config):>6}  {'-' if final is None else final:>9}")
    print(f"\n{'#':>2} {'Apellido, nombre':<28} {'Equipo':<10} Nota  Observación")
    for number, student in enumerate(students, 1):
        print(f"{number:>2} {student['Apellido'] + ', ' + student['Nombre']:<28} {student['Equipo']:<10} {student['Nota']!s:>4}  {student['Observación']}")
    print(f"\nNotas por equipo: {out_dir / 'notas.csv'}\nPara Google Sheets: {out_dir / 'notas-sheets.csv'}\nInforme: {out_dir / 'informe.md'}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # names have accents; Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clones", type=Path, help="Folder with the local clones (default: .repos-trimestre-<term>)")
    parser.add_argument("--corte", default=DEFAULT_CORTE, help=f"Corte folder under correcciones/ (default: {DEFAULT_CORTE})")
    parser.add_argument("--output", type=Path, help="Output folder (default: correcciones/resultados/<term>/<corte>)")
    parser.add_argument("--cutoff", help="Override the cutoff of corte.json (ISO 8601 with timezone)")
    parser.add_argument("--team", action="append", help="Grade only this team (repeatable)")
    parser.add_argument("--update", action="store_true", help="Clone/fetch the team repos from GitHub first")
    args = parser.parse_args()

    config_dir = ROOT / "correcciones" / args.corte
    config = load_config(config_dir / "corte.json")
    if args.cutoff:
        to_utc_iso(args.cutoff)
        config = replace(config, cutoff=args.cutoff)
    term, teams = load_active_teams(config)
    if args.team:
        wanted = {normalize(name) for name in args.team}
        teams = [item for item in teams if normalize(item["team"]) in wanted]
        if not teams:
            raise ValueError(f"No active team matches {args.team}")
    clones = args.clones or ROOT / f".repos-trimestre-{term}"
    out_dir = args.output or ROOT / "correcciones" / "resultados" / term / args.corte
    authors = load_authors(config_dir / "autores.csv")
    preliminary = datetime.now(timezone.utc) < datetime.fromisoformat(to_utc_iso(config.cutoff).replace("Z", "+00:00"))

    rows = []
    for item in teams:
        print(f"Evaluando {item['team']}...", flush=True)
        rows.append(evaluate_team(item, config, clones, out_dir, args.update))
    warnings: list[str] = []
    students = student_rows(load_delivery_list(DELIVERY_LIST_FILE), rows, config, authors, warnings)
    write_outputs(rows, students, config, out_dir, term, warnings, preliminary)
    print_summary(rows, students, config, out_dir, preliminary)
    for text in warnings:
        print(f"ADVERTENCIA: {text}")
    return 1 if any(row.error for row in rows) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
