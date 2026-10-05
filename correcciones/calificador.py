"""Grade Tarea 1 (perceptron) for every student in the active term with one command.

    python correcciones/calificador.py                    # grade everything
    python correcciones/calificador.py --update           # refresh the clones first
    python correcciones/calificador.py --team G1          # only one team

Per student file: take the commit at the cutoff from the local clones, run the program in a
sandbox against the 4 rubric cases, score them, apply late-submission penalties and teacher
decisions, and write `notas.csv` + `informe.md` (grade on the 0-20 scale).
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path

from lista import BY_TEAM, UNASSIGNED, ListEntry, assign_students, sort_key
from entregas import (ASSIGNMENT_DIR, PERCEPTRON_FILES, commit_at_cutoff, commit_date, commit_exists,
                      export_assignment, static_review, student_identity, to_utc_iso)
from rubrica import (CASE_KEYS, CaseResult, Rubric, final_grade, load_rubric, rubric_grade, score_case)
from sandbox import check_runtime, run_case

ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENT_CONFIG = ROOT / "correcciones" / "tarea-1"
STATE_FILE = ROOT / "trimestre-actual" / "estado.json"
NO_CODE_EXPLANATION = "El archivo conserva la plantilla sin código; no procesa este ejemplo ni produce una gráfica."


@dataclass
class Submission:
    team: str
    repo: str
    file: str
    commit: str = ""
    commit_date: str = ""
    student_name: str = ""
    national_id: str = ""
    status: str = "graded"          # graded | no_submission | does_not_compile | repo_error
    penalty: int = 0
    last_name: str = ""
    first_name: str = ""
    assignment: str = UNASSIGNED    # header | by_team | unassigned (see lista.py)
    notes: list[str] = field(default_factory=list)
    source_dir: Path | None = None
    cases: dict[str, CaseResult] = field(default_factory=dict)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def load_overrides(path: Path) -> list[dict]:
    """Teacher decisions pinned to an exact (team, file, commit); validated on load."""
    overrides = json.loads(path.read_text(encoding="utf-8-sig"))
    seen = set()
    for item in overrides:
        key = (item["team"], item["file"], item["commit"])
        if key in seen:
            raise ValueError(f"Duplicated teacher decision: {key}")
        seen.add(key)
        if not item.get("reason", "").strip():
            raise ValueError(f"Teacher decision without reason: {key}")
        for case, decision in item["cases"].items():
            if case not in CASE_KEYS or decision["outcome"] not in ("correct", "incorrect", "no_result") \
                    or not decision.get("explanation", "").strip():
                raise ValueError(f"Invalid teacher decision {key} / {case}")
    return overrides


def load_active_repos(state_file: Path, excluded: tuple[str, ...]) -> tuple[str, list[tuple[str, str]]]:
    state = json.loads(state_file.read_text(encoding="utf-8-sig"))
    active = [item for item in state if item.get("status") == "active" and item["team"] not in excluded]
    if not active:
        raise ValueError(f"No active teams to grade in {state_file}")
    terms = {item["term"] for item in active}
    if len(terms) != 1:
        raise ValueError(f"Expected a single term in {state_file}, found {sorted(terms)}")
    return terms.pop(), [(item["team"], item["repo"]) for item in active]


def collect_submissions(teams: list[tuple[str, str]], clones: Path, rubric: Rubric, work_dir: Path,
                        roster: dict[tuple[str, str], dict], late: dict[tuple[str, str], dict],
                        warnings: list[str]) -> list[Submission]:
    submissions = []
    for team, repo_name in teams:
        repo = clones / repo_name
        if not (repo / ".git").exists():
            for file in PERCEPTRON_FILES:
                submission = Submission(team, repo_name, file, status="repo_error")
                submission.notes.append(f"No existe el clon local {repo}; ejecutar con --update.")
                submissions.append(submission)
            continue
        cutoff_sha = commit_at_cutoff(repo, rubric.cutoff)
        for file in PERCEPTRON_FILES:
            submission = Submission(team, repo_name, file)
            sha = cutoff_sha
            accepted = late.get((team, file))
            if accepted:
                if not commit_exists(repo, accepted["commit"]):
                    warnings.append(f"Entrega tardía de {team}/{file}: el commit {accepted['commit'][:10]} no existe en el clon.")
                else:
                    sha = accepted["commit"]
                    submission.penalty = int(accepted["penalty_points"])
                    submission.notes.append(f"Entrega posterior al cierre aceptada: descuento de {submission.penalty} puntos. {accepted['reason']}")
            if sha is None:
                submission.status = "no_submission"
                submission.notes.append("Sin commits hasta el cierre.")
                submissions.append(submission)
                continue
            submission.commit, submission.commit_date = sha, commit_date(repo, sha)
            source_dir = work_dir / "sources" / repo_name / sha[:10]
            if not source_dir.exists():
                export_assignment(repo, sha, source_dir)
            submission.source_dir = source_dir / ASSIGNMENT_DIR
            path = submission.source_dir / file
            if not path.exists():
                submission.status = "no_submission"
                submission.notes.append("Archivo ausente en ese commit.")
            else:
                source = path.read_text(encoding="utf-8-sig", errors="replace")
                review = static_review(source)
                submission.student_name, submission.national_id = student_identity(source)
                if review["empty"]:
                    submission.status = "no_submission"
                    submission.notes.append("Archivo plantilla sin código ejecutable.")
                elif not review["syntax_ok"]:
                    submission.status = "does_not_compile"
                    submission.notes.append(f"No compila ({review['syntax_error']}).")
                if review["forbidden_imports"]:
                    submission.notes.append("Importa librerías fuera de matplotlib: " + ", ".join(review["forbidden_imports"]) + ".")
            fill_identity_from_roster(submission, roster.get((team, file)), warnings)
            submissions.append(submission)
    return submissions


def fill_identity_from_roster(submission: Submission, entry: dict | None, warnings: list[str]) -> None:
    """The roster only fills what the file header lacks; a conflict is reported, never silently resolved."""
    if not entry:
        return
    name, national_id = entry["student_name"].strip(), entry["national_id"].strip()
    if name and submission.student_name and name.casefold() != submission.student_name.casefold():
        warnings.append(f"{submission.team}/{submission.file}: nombre en cabecera '{submission.student_name}' difiere de la lista '{name}'.")
    elif name and not submission.student_name:
        submission.student_name = name
    if national_id and not submission.national_id:
        submission.national_id = national_id


def load_delivery_list(path: Path) -> list[ListEntry]:
    entries = [ListEntry(r["last_name"].strip(), r["first_name"].strip(), r["team"].strip()) for r in read_csv(path)]
    if len({(sort_key(entry), entry.team.casefold()) for entry in entries}) != len(entries):
        raise ValueError(f"Duplicated student in {path.name}")
    return entries


def order_by_delivery_list(submissions: list[Submission], entries: list[ListEntry], warnings: list[str]) -> list[Submission]:
    """Attach list entries to submissions and return them in delivery (alphabetical) order."""
    graded_teams = {s.team.casefold() for s in submissions}
    entries = [entry for entry in entries if entry.team.casefold() in graded_teams]
    assigned, list_warnings = assign_students([(s.team, s.file, s.student_name) for s in submissions], entries)
    warnings.extend(list_warnings)
    position = {entry: index for index, entry in enumerate(sorted(entries, key=sort_key))}
    for s in submissions:
        match = assigned.get((s.team, s.file))
        if not match:
            continue
        entry, how = match
        s.last_name, s.first_name, s.assignment = entry.last_name, entry.first_name, how
        if how == BY_TEAM:
            s.student_name = s.student_name or entry.full_name
            s.notes.append("Asignación PROVISIONAL por equipo: el archivo no trae nombre; confirmar el estudiante.")

    def order(s: Submission) -> tuple[int, str, str]:
        match = assigned.get((s.team, s.file))
        return (position[match[0]] if match else len(position)), s.team.casefold(), s.file

    return sorted(submissions, key=order)


def apply_overrides(submissions: list[Submission], overrides: list[dict], warnings: list[str]) -> None:
    by_key = {(s.team, s.file, s.commit): s for s in submissions}
    for item in overrides:
        submission = by_key.get((item["team"], item["file"], item["commit"]))
        if submission is None:
            warnings.append(
                f"Decisión docente obsoleta: {item['team']}/{item['file']}@{item['commit'][:10]} ya no "
                "corresponde a ninguna entrega evaluada (cambió el commit); NO se aplicó.")
            continue
        submission.notes.append("Decisión docente aplicada: " + item["reason"])
        for case, decision in item["cases"].items():
            submission.cases[case] = CaseResult(decision["outcome"], decision["explanation"], False, "teacher_decision")


def runnable_cases(submission: Submission) -> list[str]:
    if submission.status != "graded":
        return []
    return [case for case in CASE_KEYS if case not in submission.cases]


def run_all(submissions: list[Submission], evidence_dir: Path, workers: int, timeout: int) -> None:
    jobs = [(s, case) for s in submissions for case in runnable_cases(s)]
    if not jobs:
        return

    def execute(job):
        submission, case = job
        out = evidence_dir / submission.team / submission.file.removesuffix(".py") / case
        evidence = run_case(submission.source_dir, submission.file, case, out, timeout)
        print(f"  {submission.team}/{submission.file} {case}: {evidence.status}, plots={evidence.plots}", flush=True)
        return job, score_case(case, evidence)

    print(f"Ejecutando {len(jobs)} casos en el sandbox ({workers} en paralelo)...", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for (submission, case), result in pool.map(execute, jobs):
            submission.cases[case] = result


def finalize_unrunnable(submissions: list[Submission]) -> None:
    for submission in submissions:
        for case in CASE_KEYS:
            if case in submission.cases:
                continue
            if submission.status == "graded":
                raise RuntimeError(f"Case without result: {submission.team}/{submission.file}/{case}")
            reason = NO_CODE_EXPLANATION if submission.status == "no_submission" else "No hay ejecución posible; " + " ".join(submission.notes)
            submission.cases[case] = CaseResult("no_result", reason, False, "no_submission")


def build_rows(submissions: list[Submission], rubric: Rubric) -> list[dict]:
    rows = []
    for s in submissions:
        outcomes = {case: s.cases[case].outcome for case in CASE_KEYS}
        points, rubric_value = rubric_grade(rubric, outcomes)
        row = {
            "last_name": s.last_name, "first_name": s.first_name, "assignment": s.assignment,
            "team": s.team, "file": s.file, "student_name": s.student_name, "national_id": s.national_id,
            "commit": s.commit, "commit_date": s.commit_date, "status": s.status,
            **{case: rubric.points(case, outcomes[case]) for case in CASE_KEYS},
            "rubric_points": points, "rubric_grade": rubric_value, "penalty_points": s.penalty,
            "final_grade": final_grade(rubric, rubric_value, s.penalty),
            "needs_review": ", ".join(case for case in CASE_KEYS if s.cases[case].needs_review),
            "comment": " ".join(f"{rubric.description(case)} ({rubric.points(case, outcomes[case])}/{rubric.criteria[case]['correct']}): "
                                f"{s.cases[case].explanation}" for case in CASE_KEYS) + (" " + " ".join(s.notes) if s.notes else ""),
        }
        rows.append(row)
    return rows


def write_outputs(rows: list[dict], submissions: list[Submission], rubric: Rubric, out_dir: Path,
                  term: str, warnings: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "notas.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # One row per student in delivery order: the Nota column pastes straight into Google Sheets.
    with (out_dir / "notas-sheets.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["Apellido", "Nombre", "Equipo", "Nota", "Observación"])
        for row in rows:
            observation = {BY_TEAM: "Provisional: asignado por equipo",
                           UNASSIGNED: "Sin entrada en la lista de entrega"}.get(row["assignment"], "")
            writer.writerow([row["last_name"], row["first_name"], row["team"], row["final_grade"], observation])

    lines = [f"# Corrección automática: {rubric.name} ({term})", "",
             f"Cierre: {rubric.cutoff}. Cada archivo usa el último commit anterior al cierre, salvo las "
             "entregas tardías aceptadas expresamente. Los puntajes de la rúbrica salen de ejecutar cada "
             "programa en un sandbox sin red contra los cuatro casos; la columna **Revisar** señala los "
             "casos donde conviene mirar la gráfica (carpeta `evidence/`) porque el criterio es visual.", "",
             f"Escala: nota por rúbrica proporcional sobre {rubric.maximum_grade}, mínimo {rubric.minimum_grade}; "
             "luego se resta el descuento por entrega tardía.", "",
             "| # | Apellido, nombre | Equipo / archivo | C1 | C2 | C3 | C4 | Rúbrica | Descuento | Nota | Revisar |",
             "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for number, row in enumerate(rows, 1):
        who = display_name(row) + (" *(provisional)*" if row["assignment"] == BY_TEAM else "")
        lines.append(f"| {number} | {who} | {row['team']}/{row['file']} | " + " | ".join(str(row[case]) for case in CASE_KEYS)
                     + f" | {row['rubric_grade']} | {row['penalty_points']} | **{row['final_grade']}** | {row['needs_review'] or '-'} |")
    if warnings:
        lines += ["", "## Advertencias", ""] + [f"- {text}" for text in warnings]
    lines += ["", "## Detalle por archivo", ""]
    for s, row in zip(submissions, rows):
        who = display_name(row)
        lines += [f"### {who} — {row['team']}/{row['file']} — {row['final_grade']}/{rubric.maximum_grade}", "",
                  f"Commit evaluado: `{row['commit'] or 'ninguno'}` ({row['commit_date'] or 'sin fecha'}). Estado: {s.status}.", ""]
        for case in CASE_KEYS:
            result = s.cases[case]
            tag = " (decisión docente)" if result.source == "teacher_decision" else ""
            graph = ""
            figure = out_dir / "evidence" / s.team / s.file.removesuffix(".py") / case
            pngs = sorted(figure.glob("grafico_*.png")) if figure.exists() else []
            if pngs:
                graph = f" [Gráfica](evidence/{s.team}/{s.file.removesuffix('.py')}/{case}/{pngs[-1].name})"
            lines.append(f"- **{rubric.description(case)}: {row[case]}/{rubric.criteria[case]['correct']}{tag}.** {result.explanation}{graph}")
        if s.notes:
            lines += ["", *[f"> {note}" for note in s.notes]]
        lines.append("")
    (out_dir / "informe.md").write_text("\n".join(lines), encoding="utf-8")


def display_name(row: dict) -> str:
    """'Apellido, Nombre' from the delivery list; falls back to the name found in the file header."""
    if row["last_name"]:
        return f"{row['last_name']}, {row['first_name']}"
    return row["student_name"] or "Sin nombre"


def print_summary(rows: list[dict], out_dir: Path) -> None:
    print(f"\n{'#':>2} {'Apellido, nombre':<26} {'Equipo':<10} {'Archivo':<16} C1  C2  C3  C4  Rúb  Desc  Nota  Revisar")
    for number, row in enumerate(rows, 1):
        who = display_name(row) + (" *" if row["assignment"] == BY_TEAM else "")
        print(f"{number:>2} {who[:25]:<26} {row['team']:<10} {row['file']:<16} "
              + "  ".join(f"{row[case]:>2}" for case in CASE_KEYS)
              + f"  {row['rubric_grade']:>3}  {row['penalty_points']:>4}  {row['final_grade']:>4}  {row['needs_review'] or '-'}")
    if any(row["assignment"] == BY_TEAM for row in rows):
        print("\n* asignación provisional por equipo (el archivo no trae nombre)")
    print(f"\nNotas: {out_dir / 'notas.csv'}\nPara Google Sheets: {out_dir / 'notas-sheets.csv'}\nInforme: {out_dir / 'informe.md'}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # student names have accents; Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clones", type=Path, help="Folder with the local clones (default: .repos-trimestre-<term>)")
    parser.add_argument("--output", type=Path, help="Output folder (default: correcciones/resultados/<term>/tarea-1)")
    parser.add_argument("--cutoff", help="Override the cutoff of tarea.json (ISO 8601 with timezone)")
    parser.add_argument("--team", action="append", help="Grade only this team (repeatable)")
    parser.add_argument("--update", action="store_true", help="Run tareas/verify_submissions.py first to refresh the clones")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=40, help="Seconds per case")
    args = parser.parse_args()

    rubric = load_rubric(ASSIGNMENT_CONFIG / "tarea.json")
    if args.cutoff:
        to_utc_iso(args.cutoff)
        rubric = replace(rubric, cutoff=args.cutoff)
    term, teams = load_active_repos(STATE_FILE, rubric.excluded_teams)
    if args.team:
        wanted = {name.casefold() for name in args.team}
        teams = [item for item in teams if item[0].casefold() in wanted]
        if not teams:
            raise ValueError(f"No active team matches {args.team}")
    if args.update:
        subprocess.run([sys.executable, str(ROOT / "tareas" / "verify_submissions.py")], check=True)
    clones = args.clones or ROOT / f".repos-trimestre-{term}"
    out_dir = args.output or ROOT / "correcciones" / "resultados" / term / "tarea-1"
    check_runtime()

    warnings: list[str] = []
    delivery_list = load_delivery_list(ASSIGNMENT_CONFIG / "lista-entrega.csv")
    roster = {(r["team"], r["file"]): r for r in read_csv(ASSIGNMENT_CONFIG / "alumnos.csv")}
    late = {(r["team"], r["file"]): r for r in read_csv(ASSIGNMENT_CONFIG / "entregas-tardias.csv")}
    overrides = load_overrides(ASSIGNMENT_CONFIG / "decisiones-docente.json")

    submissions = collect_submissions(teams, clones, rubric, out_dir, roster, late, warnings)
    # Only report obsolete decisions/late entries for the teams actually graded in this run.
    graded_teams = {team for team, _ in teams}
    apply_overrides(submissions, [o for o in overrides if o["team"] in graded_teams], warnings)
    run_all(submissions, out_dir / "evidence", args.workers, args.timeout)
    finalize_unrunnable(submissions)
    submissions = order_by_delivery_list(submissions, delivery_list, warnings)
    rows = build_rows(submissions, rubric)
    write_outputs(rows, submissions, rubric, out_dir, term, warnings)
    print_summary(rows, out_dir)
    for text in warnings:
        print(f"ADVERTENCIA: {text}")
    return 1 if any(s.status == "repo_error" for s in submissions) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
