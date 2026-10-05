"""Grade the `corte-preguntas-1` deliverable of every team with one command.

    python correcciones/calificador_corte.py            # grade everything
    python correcciones/calificador_corte.py --update   # fetch the team repos from GitHub first
    python correcciones/calificador_corte.py --team G1  # only one team

Per team: fetch (optional), take the `preguntas.json` of the last commit before the cutoff, run the
authoritative unit tests (format, requested questions, easy and hard questions per reading), flag
commits pushed after the cutoff, and write `notas.csv` (per team), `notas-sheets.csv` (per student,
alphabetical, ready to paste into Google Sheets) and `informe.md`.
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
from entregas import commit_at_cutoff, commit_date, commit_exists, commits_after_cutoff, export_assignment, remote_ref, to_utc_iso
from lista import ListEntry, normalize, sort_key

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "correcciones" / "corte-preguntas-1"
STATE_FILE = ROOT / "trimestre-actual" / "estado.json"
DELIVERY_LIST_FILE = ROOT / "trimestre-actual" / "lista-entrega.csv"


@dataclass
class TeamRow:
    team: str
    repo: str
    url: str
    commit: str = ""
    commit_date: str = ""
    late_commit_dates: list[str] = field(default_factory=list)
    penalty: int = 0
    notes: list[str] = field(default_factory=list)
    result: CorteResult | None = None
    error: str = ""

    @property
    def on_time(self) -> bool:
        return not self.late_commit_dates

    def grade(self, config: CorteConfig) -> int | None:
        if self.result is None:
            return None
        return final_grade(config, self.result.points, self.penalty)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def load_active_teams(config: CorteConfig) -> tuple[str, list[dict]]:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
    teams = [item for item in state if item.get("status") == "active" and item["team"] not in config.excluded_teams]
    if not teams:
        raise ValueError(f"No active teams to grade in {STATE_FILE}")
    terms = {item["term"] for item in teams}
    if len(terms) != 1:
        raise ValueError(f"Expected a single term in {STATE_FILE}, found {sorted(terms)}")
    return terms.pop(), teams


def evaluate_team(item: dict, config: CorteConfig, clones: Path, work_dir: Path, accepted: dict | None, update: bool) -> TeamRow:
    row = TeamRow(team=item["team"], repo=item["repo"], url=item["url"])
    repo = clones / item["repo"]
    try:
        if update:
            sync_clone(item["url"], repo)
        if not (repo / ".git").exists():
            raise RuntimeError(f"No existe el clon local {repo}; ejecutar con --update.")
        ref = remote_ref(repo)
        sha = commit_at_cutoff(repo, config.cutoff, ref)
        row.late_commit_dates = commits_after_cutoff(repo, config.cutoff, ref, config.folder)
        if accepted:
            if commit_exists(repo, accepted["commit"]):
                sha, row.penalty = accepted["commit"], int(accepted["penalty_points"])
                row.notes.append(f"Entrega posterior al cierre aceptada: descuento de {row.penalty} puntos. {accepted['reason']}")
            else:
                row.notes.append(f"La entrega tardía aceptada ({accepted['commit'][:10]}) no existe en el clon; no se aplicó.")
        questions_file = work_dir / "sources" / item["repo"] / "missing" / config.deliverable
        if sha:
            row.commit, row.commit_date = sha, commit_date(repo, sha)
            exported = export_assignment(repo, sha, work_dir / "sources" / item["repo"] / sha[:10], config.folder)
            questions_file = exported / config.deliverable
        else:
            row.notes.append("Sin commits hasta el cierre.")
        outcomes = run_tests(config.test_file, questions_file.resolve(), work_dir / "evidence" / item["team"])
        row.result = score(config, outcomes)
        if row.result.tests_passed == 0:
            row.notes.append("Ninguna prueba pasó: el archivo está vacío, ilegible o conserva el texto de la plantilla.")
    except (RuntimeError, OSError, ValueError) as exc:
        row.error = str(exc)
    return row


def load_delivery_list(path: Path) -> list[ListEntry]:
    return [ListEntry(r["last_name"].strip(), r["first_name"].strip(), r["team"].strip()) for r in read_csv(path)]


def student_rows(entries: list[ListEntry], rows: list[TeamRow], config: CorteConfig, warnings: list[str]) -> list[dict]:
    """One row per student in alphabetical delivery order; every member gets the grade of the team."""
    by_team = {normalize(row.team): row for row in rows}
    result = []
    for entry in sorted(entries, key=sort_key):
        team_row = by_team.get(normalize(entry.team))
        if team_row is None:
            continue   # team not graded in this run (--team filter)
        grade = team_row.grade(config)
        observations = []
        if grade is None:
            observations.append("Sin resultado: " + team_row.error)
        if not team_row.on_time:
            observations.append(f"Entrega tardía ({len(team_row.late_commit_dates)} commits después del cierre)")
        result.append({"Apellido": entry.last_name, "Nombre": entry.first_name, "Equipo": entry.team,
                       "Nota": "" if grade is None else grade, "Observación": "; ".join(observations)})
    listed = {normalize(entry.team) for entry in entries}
    for row in rows:
        if normalize(row.team) not in listed:
            warnings.append(f"El equipo {row.team} no tiene estudiantes en lista-entrega.csv.")
    return result


def write_outputs(rows: list[TeamRow], students: list[dict], config: CorteConfig, out_dir: Path, term: str,
                  warnings: list[str], preliminary: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [criterion.key for criterion in config.criteria]
    with (out_dir / "notas.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["team", "repo", "commit", "commit_date", "on_time", "late_commits", "last_late_commit",
                         *keys, "tests_passed", "tests_total", "points", "penalty_points", "final_grade", "error"])
        for row in rows:
            scores = {s.key: s for s in row.result.scores} if row.result else {}
            writer.writerow([row.team, row.repo, row.commit, row.commit_date, "yes" if row.on_time else "no",
                             len(row.late_commit_dates), row.late_commit_dates[0] if row.late_commit_dates else "",
                             *[f"{float(scores[k].points):.2f}" if k in scores else "" for k in keys],
                             row.result.tests_passed if row.result else "", row.result.tests_total if row.result else "",
                             f"{float(row.result.points):.2f}" if row.result else "", row.penalty,
                             row.grade(config) if row.result else "", row.error])
    with (out_dir / "notas-sheets.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["Apellido", "Nombre", "Equipo", "Nota", "Observación"])
        writer.writeheader()
        writer.writerows(students)

    lines = [f"# Corrección automática: {config.name} ({term})", ""]
    if preliminary:
        lines += ["> **PRELIMINAR:** el cierre aún no ha ocurrido; se evaluó el último commit actual de cada equipo.", ""]
    lines += [f"Cierre: {config.cutoff}. Cada equipo se evalúa con el `{config.deliverable}` del último commit anterior al "
              "cierre, ejecutando las mismas pruebas unitarias que corren los estudiantes (formato, preguntas solicitadas, "
              "fáciles y difíciles por lectura). Cada criterio vale 5 puntos, proporcional a las pruebas que pasan; los "
              "commits posteriores al cierre no se evalúan y se señalan como entrega tardía.", "",
              "| Equipo | A tiempo | " + " | ".join(c.key for c in config.criteria) + " | Pruebas | Nota |",
              "|---|---|" + "---:|" * len(config.criteria) + "---:|---:|"]
    for row in rows:
        scores = {s.key: s for s in row.result.scores} if row.result else {}
        late = "sí" if row.on_time else f"**no** ({len(row.late_commit_dates)} commits)"
        lines.append(f"| {row.team} | {late} | " + " | ".join(f"{float(scores[c.key].points):.1f}/{c.points}" if c.key in scores else "-" for c in config.criteria)
                     + f" | {row.result.tests_passed}/{row.result.tests_total} | **{row.grade(config)}** |" if row.result
                     else f"| {row.team} | {late} | " + " | ".join("-" for _ in config.criteria) + " | - | **sin resultado** |")
    lines += ["", "## Notas por estudiante (orden alfabético)", "", "| # | Apellido, nombre | Equipo | Nota | Observación |", "|---:|---|---|---:|---|"]
    for number, student in enumerate(students, 1):
        lines.append(f"| {number} | {student['Apellido']}, {student['Nombre']} | {student['Equipo']} | **{student['Nota']}** | {student['Observación']} |")
    if warnings:
        lines += ["", "## Advertencias", ""] + [f"- {text}" for text in warnings]
    lines += ["", "## Detalle por equipo", ""]
    for row in rows:
        lines += [f"### {row.team} — {row.grade(config) if row.result else 'sin resultado'}/{config.maximum_grade}", "",
                  f"Commit evaluado: `{row.commit or 'ninguno'}` ({row.commit_date or 'sin fecha'}). "
                  + ("Entregó a tiempo." if row.on_time else f"Hay {len(row.late_commit_dates)} commits tardíos en `{config.folder}/`; el último: {row.late_commit_dates[0]}."), ""]
        if row.error:
            lines += [f"**Error:** {row.error}", ""]
        if row.result:
            for criterion in config.criteria:
                criterion_score = next(s for s in row.result.scores if s.key == criterion.key)
                lines.append(f"- **{criterion.description}: {float(criterion_score.points):.1f}/{criterion.points}** "
                             f"({criterion_score.passed}/{criterion_score.total} pruebas)")
                for name in criterion.tests:
                    for outcome in row.result.outcomes.get(name, []):
                        if not outcome.passed:
                            lines.append(f"  - ✗ `{name}`: {outcome.message or 'falló'}")
        lines += [f"> {note}" for note in row.notes] + [""]
    (out_dir / "informe.md").write_text("\n".join(lines), encoding="utf-8")


def print_summary(rows: list[TeamRow], students: list[dict], config: CorteConfig, out_dir: Path, preliminary: bool) -> None:
    if preliminary:
        print("\n*** PRELIMINAR: el cierre aún no ha ocurrido; se evalúa el último commit actual ***")
    print(f"\n{'Equipo':<12} {'A tiempo':<22} " + " ".join(f"{c.key:>6}" for c in config.criteria) + "  Pruebas  Nota")
    for row in rows:
        late = "sí" if row.on_time else f"NO ({len(row.late_commit_dates)} tardíos)"
        if row.result is None:
            print(f"{row.team:<12} {late:<22} ERROR: {row.error}")
            continue
        scores = {s.key: s for s in row.result.scores}
        print(f"{row.team:<12} {late:<22} " + " ".join(f"{float(scores[c.key].points):>6.1f}" for c in config.criteria)
              + f"  {row.result.tests_passed:>3}/{row.result.tests_total:<3}  {row.grade(config):>4}")
    print(f"\n{'#':>2} {'Apellido, nombre':<28} {'Equipo':<10} Nota  Observación")
    for number, student in enumerate(students, 1):
        print(f"{number:>2} {student['Apellido'] + ', ' + student['Nombre']:<28} {student['Equipo']:<10} {student['Nota']!s:>4}  {student['Observación']}")
    print(f"\nNotas por equipo: {out_dir / 'notas.csv'}\nPara Google Sheets: {out_dir / 'notas-sheets.csv'}\nInforme: {out_dir / 'informe.md'}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # names have accents; Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clones", type=Path, help="Folder with the local clones (default: .repos-trimestre-<term>)")
    parser.add_argument("--output", type=Path, help="Output folder (default: correcciones/resultados/<term>/corte-preguntas-1)")
    parser.add_argument("--cutoff", help="Override the cutoff of corte.json (ISO 8601 with timezone)")
    parser.add_argument("--team", action="append", help="Grade only this team (repeatable)")
    parser.add_argument("--update", action="store_true", help="Clone/fetch the team repos from GitHub first")
    args = parser.parse_args()

    config = load_config(CONFIG_DIR / "corte.json")
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
    out_dir = args.output or ROOT / "correcciones" / "resultados" / term / "corte-preguntas-1"
    late = {r["team"]: r for r in read_csv(CONFIG_DIR / "entregas-tardias.csv")}
    preliminary = datetime.now(timezone.utc) < datetime.fromisoformat(to_utc_iso(config.cutoff).replace("Z", "+00:00"))

    rows = []
    for item in teams:
        print(f"Evaluando {item['team']}...", flush=True)
        rows.append(evaluate_team(item, config, clones, out_dir, late.get(item["team"]), args.update))
    warnings: list[str] = []
    students = student_rows(load_delivery_list(DELIVERY_LIST_FILE), rows, config, warnings)
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
