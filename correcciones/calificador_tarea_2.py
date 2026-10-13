"""Grade Tarea 2 from immutable Git snapshots; regenerate private CSVs and individual analysis."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from calificador import (Submission, apply_overrides, build_rows, fill_identity_from_roster,
                         load_active_repos, load_delivery_list, load_overrides, order_by_delivery_list,
                         pick_best_versions, print_summary, read_csv, write_outputs)
from entregas import (commit_at_cutoff, commit_date, commit_exists, commits_after_cutoff,
                      export_assignment, git, remote_ref, static_review, student_identity, to_utc_iso)
from multicapa import CASE_KEYS, FILES, FOLDER, console_answers, load_profiles, score_trace, select_network
from lista import normalize
from rubrica import CaseResult, load_rubric
from sandbox import check_runtime, isolated_command

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "correcciones" / "tarea-2"
ALLOWED_IMPORTS = set(sys.stdlib_module_names) | {"numpy", "pandas", "matplotlib", "mpl_toolkits"}


def refresh_clones(clones: Path, teams: list[str], excluded: tuple[str, ...]) -> None:
    """Delegate all clone/fetch/fast-forward work to the professor's term script."""
    shell = shutil.which("pwsh") or (shutil.which("powershell") if sys.platform == "win32" else None)
    if shell is None:
        raise RuntimeError("PowerShell is required for --update. Run scripts/traer-repos-trimestre.ps1 first, "
                           "then grade without --update.")
    script = ROOT / "scripts" / "traer-repos-trimestre.ps1"
    if not script.is_file():
        raise RuntimeError(f"Missing official refresh script: {script}")

    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    # -File cannot reliably bind multiple string[] values on all PowerShell versions.
    # Quote each literal in -Command; paths/team names must never become shell code.
    command = (f"& {literal(str(script))} -StatusPath {literal(str(ROOT / 'trimestre-actual/estado.json'))} "
               f"-Destination {literal(str(clones))} "
               f"-Team @({','.join(literal(team) for team in teams)}) "
               f"-ExcludeTeams @({','.join(literal(team) for team in excluded)})")
    subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", command], check=True)


def build_submission(team, repo, filename, sha, penalty, version, output, roster, warnings):
    submission = Submission(team, repo.name, filename, penalty=penalty, version=version)
    if not sha:
        submission.status = "no_submission"
        submission.notes.append("Sin versión disponible al cierre.")
    else:
        submission.commit, submission.commit_date = sha, commit_date(repo, sha)
        # Fresh read-only snapshots avoid stale data and Windows/WSL directory deletion permissions.
        sources = output / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix=f"{repo.name}-{sha}-", dir=sources))
        submission.source_dir = export_assignment(repo, sha, destination, folder=FOLDER)
        path = submission.source_dir / filename
        if not path.is_file():
            submission.status = "no_submission"
            submission.notes.append("Archivo ausente en este commit.")
        else:
            source = path.read_text(encoding="utf-8-sig", errors="replace")
            submission.student_name, submission.national_id = student_identity(source)
            if not submission.student_name:
                # Accept a plain name comment only when it matches the official roster uniquely.
                header_names = {normalize(line.lstrip()[1:].strip()) for line in source.splitlines()[:25]
                                if line.lstrip().startswith('#')}
                matches = [entry for entry in load_delivery_list(ROOT / 'trimestre-actual/lista-entrega.csv')
                           if entry.team == team and normalize(entry.full_name) in header_names]
                if len(matches) == 1:
                    submission.student_name = matches[0].full_name
            review = static_review(source, ALLOWED_IMPORTS)
            if review["empty"]:
                submission.status = "no_submission"
                submission.notes.append("Plantilla sin código ejecutable.")
            elif not review["syntax_ok"]:
                submission.status = "does_not_compile"
                submission.notes.append(review["syntax_error"])
            # Review every local helper too; neural frameworks are not authorized for this assignment.
            pending, visited = [path], set()
            while pending:
                helper = pending.pop()
                if helper in visited:
                    continue
                visited.add(helper)
                checked = static_review(helper.read_text(encoding="utf-8-sig", errors="replace"), ALLOWED_IMPORTS)
                local_modules = {p.stem for p in submission.source_dir.glob("*.py")}
                forbidden = set(checked["forbidden_imports"]) - local_modules
                if forbidden:
                    submission.status = "forbidden_imports"
                    submission.notes.append(f"{helper.name}: importaciones no permitidas: {', '.join(sorted(forbidden))}.")
                if checked["syntax_ok"]:
                    tree = ast.parse(helper.read_text(encoding="utf-8-sig", errors="replace"))
                    for node in ast.walk(tree):
                        modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                                  [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                        pending.extend(submission.source_dir / f"{module.split('.')[0]}.py"
                                       for module in modules if module.split('.')[0] in local_modules)
    fill_identity_from_roster(submission, roster.get((team, filename)), warnings)
    submission.evidence_path = f"evidence/{team}/{Path(filename).stem}/{sha or 'missing'}"
    return submission


def collect_submissions(teams, clones, rubric, output, roster, late, warnings, networks=None):
    submissions = []
    for team, repo_name in teams:
        repo = clones / repo_name
        if not (repo / ".git").is_dir():
            raise RuntimeError(f"Missing clone {repo}; run with --update")
        ref = remote_ref(repo)
        cutoff_sha = commit_at_cutoff(repo, rubric.cutoff, ref)
        latest_sha = git(repo, "rev-parse", ref)
        for filename in FILES:
            accepted = late.get((team, filename))
            if accepted:
                if not accepted["reason"].strip() or not commit_exists(repo, accepted["commit"]):
                    raise ValueError(f"Invalid accepted submission: {team}/{filename}")
                submissions.append(build_submission(team, repo, filename, accepted["commit"],
                                   int(accepted["penalty_points"]), "accepted", output, roster, warnings))
                submissions[-1].notes.append("Excepción de tardanza: " + accepted["reason"])
                continue
            submissions.append(build_submission(team, repo, filename, cutoff_sha, 0, "cutoff", output, roster, warnings))
            # The individual network is part of the submission; a weights-only late change also counts.
            paths = [f"{FOLDER}/{filename}"]
            number = Path(filename).stem.rsplit('_', 1)[1]
            paths += [f"{FOLDER}/red_{d}d_{c}clases_{number}.csv" for d, c in ((2, 2), (3, 4))]
            paths += [f"{FOLDER}/{value}" for value in (networks or {}).get((team, filename), {}).values() if value]
            dates = sorted({date for path in paths for date in
                            commits_after_cutoff(repo, rubric.cutoff, ref, folder=path)}, reverse=True)
            if dates:
                item = build_submission(team, repo, filename, latest_sha, rubric.late_penalty_points,
                                        "late", output, roster, warnings)
                item.late_commits = dates
                submissions.append(item)
    return submissions


def prepare_data(output: Path) -> Path:
    data = output / "inputs"
    data.mkdir(parents=True, exist_ok=True)
    given = ROOT / "repo-template" / FOLDER / "assets"
    for path in sorted(given.glob("*.csv")) + sorted((CONFIG / "casos").glob("*.csv")):
        shutil.copyfile(path, data / path.name)
    for d, c in ((2, 2), (3, 4)):
        for prefix in (f"{d}-d_{c}-class", f"hidden_{d}d_{c}class"):
            for split in ("train", "test"):
                path = data / f"{prefix}_{split}.csv"
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if reader.fieldnames != [*(f"x{i}" for i in range(1, d + 1)), "y"]:
                        raise ValueError(f"Unexpected dataset header: {path}")
                    rows = list(reader)
                    labels = {float(row['y']) for row in rows}
                    if not rows or len(labels) != c:
                        raise ValueError(f"Missing classes or rows: {path}")
    return data


def run_case(submission, case, data, output, timeout, seed, spec):
    out = output / submission.evidence_path / case
    out.mkdir(parents=True, exist_ok=True)
    for stale in (*out.glob("grafico_*.png"), out / "traza.json"):
        stale.unlink(missing_ok=True)
    dimensions, classes = (2, 2) if "2d_2class" in case else (3, 4)
    try:
        network, metadata = select_network(submission.source_dir, submission.file, dimensions, classes, spec.get("network"))
    except (ValueError, OSError) as exc:
        return CaseResult("no_result", str(exc) + ". Confirmar nombre de red y pertenencia al estudiante.", True)
    network_path = "/src/" + network.relative_to(submission.source_dir.resolve()).as_posix()
    if case.startswith("hidden") and metadata["e"] == 0:
        return CaseResult("no_result", "La red entregada registra cero épocas; sus hiperparámetros no permiten este entrenamiento.", True)
    test_name = (f"{dimensions}-d_{classes}-class" if case.startswith("given")
                 else f"hidden_{dimensions}d_{classes}class") + "_test.csv"
    test_csv = "/data/" + test_name
    answers = spec.get("answers", console_answers(case, metadata, network_path))
    substitutions = {"{network}": network_path, "{test}": test_csv,
                     "{train}": f"/data/hidden_{dimensions}d_{classes}class_train.csv",
                     **{f"{{{key}}}": str(value) for key, value in metadata.items()}}
    answers = [substitutions.get(answer, answer) for answer in answers]
    if test_csv not in answers:
        raise ValueError(f"Console profile must include the test CSV: {submission.file}/{case}")
    job = {"answers": answers, "seed": seed, "metadata": metadata, "network": network_path,
           "test_csv": test_csv, "cpu_seconds": timeout}
    (out / "job.json").write_text(json.dumps(job), encoding="utf-8")
    command = isolated_command(submission.source_dir, out, data,
                               ROOT / "correcciones" / "multicapa_runner.py",
                               ["/src/" + submission.file, "/out/job.json"])
    try:
        completed = subprocess.run(command, capture_output=True, timeout=timeout,
                                   text=True, encoding="utf-8", errors="replace")
        status = "ok" if completed.returncode == 0 else f"error_{completed.returncode}"
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
    (out / "salida.txt").write_text(stdout, encoding="utf-8")
    (out / "errores.txt").write_text(stderr, encoding="utf-8")
    trace_path = out / "traza.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else {}
    with (data / test_name).open(encoding="utf-8", newline="") as stream:
        labels = [float(row["y"]) for row in csv.DictReader(stream)]
    counts = [labels.count(label) for label in sorted(set(labels))]
    result = score_trace(trace, counts, status)
    (out / "resultado.json").write_text(json.dumps({"status": status, "outcome": result.outcome,
            "explanation": result.explanation, "needs_review": result.needs_review}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Run scripts/traer-repos-trimestre.ps1 before grading")
    parser.add_argument("--team", action="append")
    parser.add_argument("--clones", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cutoff")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--seed", type=int, default=2526)
    args = parser.parse_args()
    if args.timeout < 1:
        raise ValueError("timeout must be positive")
    rubric = load_rubric(CONFIG / "tarea.json")
    if tuple(rubric.criteria) != CASE_KEYS:
        raise ValueError(f"Unexpected Tarea 2 criteria: {tuple(rubric.criteria)}")
    rubric = replace(rubric, cutoff=args.cutoff or rubric.cutoff)
    to_utc_iso(rubric.cutoff)
    term, teams = load_active_repos(ROOT / "trimestre-actual" / "estado.json", rubric.excluded_teams)
    if args.team:
        wanted = {team.casefold() for team in args.team}
        teams = [item for item in teams if item[0].casefold() in wanted]
        if not teams:
            raise ValueError("No matching active teams")
    clones = (args.clones or ROOT / f".repos-trimestre-{term}").resolve()
    output = (args.output or ROOT / "correcciones" / "resultados" / term / "tarea-2").resolve()
    if output == ROOT or output.is_relative_to(clones) or clones.is_relative_to(output):
        raise ValueError("Output must be separate from clones and the repository root")
    if args.update:
        refresh_clones(clones, [team for team, _ in teams], rubric.excluded_teams)
    warnings = []
    preliminary = datetime.fromisoformat(rubric.cutoff) > datetime.now(timezone.utc)
    if preliminary:
        warnings.append("PRELIMINAR: no ha llegado el cierre configurado; confirmar la fecha antes de publicar notas.")
    data = prepare_data(output)
    roster = {(row["team"], row["file"]): row for row in read_csv(CONFIG / "alumnos.csv")}
    late = {(row["team"], row["file"]): row for row in read_csv(CONFIG / "entregas-tardias.csv")}
    networks = {(row["team"], row["file"]): {"2d": row["network_2d"], "3d": row["network_3d"]}
                for row in read_csv(CONFIG / "redes-entregadas.csv")}
    submissions = collect_submissions(teams, clones, rubric, output, roster, late, warnings, networks)
    profiles = load_profiles(CONFIG / "perfiles-consola.json")
    evaluated = {(s.team, s.file, s.commit) for s in submissions}
    for profile in profiles:
        if profile["team"] in {team for team, _ in teams} and (profile["team"], profile["file"], profile["commit"]) not in evaluated:
            warnings.append(f"Perfil de consola obsoleto: {profile['team']}/{profile['file']}@{profile['commit']}; no se aplicó.")
    apply_overrides(submissions, [item for item in load_overrides(CONFIG / "decisiones-docente.json", CASE_KEYS)
                    if item["team"] in {team for team, _ in teams}], warnings)
    if any(s.status == "graded" and set(s.cases) != set(CASE_KEYS) for s in submissions):
        check_runtime(("matplotlib", "numpy", "pandas"))
    for submission in submissions:
        profile = next((p for p in profiles if (p["team"], p["file"], p["commit"]) ==
                        (submission.team, submission.file, submission.commit)), {"cases": {}})
        for case in CASE_KEYS:
            if case in submission.cases:
                continue
            if submission.status != "graded":
                submission.cases[case] = CaseResult("no_result", " ".join(submission.notes), False)
            else:
                print(f"Running {submission.team}/{submission.file}@{submission.commit[:10]}: {case}", flush=True)
                spec = dict(profile["cases"].get(case, {}))
                network = networks.get((submission.team, submission.file), {}).get("2d" if "2d_" in case else "3d")
                if network and "network" not in spec:
                    spec["network"] = network
                submission.cases[case] = run_case(submission, case, data, output, args.timeout,
                                                   args.seed, spec)
    all_versions = list(submissions)
    submissions = pick_best_versions(submissions, rubric, warnings)
    for chosen in submissions:
        unresolved = [s for s in all_versions if (s.team, s.file) == (chosen.team, chosen.file)
                      and any(result.needs_review for result in s.cases.values())]
        if unresolved:
            chosen.notes.append("Nota propuesta: hay evidencia o versiones pendientes de revisión docente.")
            for key in CASE_KEYS:
                chosen.cases[key].needs_review |= any(s.cases[key].needs_review for s in unresolved)
    submissions = order_by_delivery_list(submissions,
                   load_delivery_list(ROOT / "trimestre-actual" / "lista-entrega.csv"), warnings)
    rows = build_rows(submissions, rubric)
    write_outputs(rows, submissions, rubric, output, term, warnings, preliminary)
    print_summary(rows, output, CASE_KEYS)
    for message in warnings:
        print("ADVERTENCIA: " + message)
    manifest = {"central_commit": git(ROOT, "rev-parse", "HEAD"), "cutoff": rubric.cutoff,
                "seed": args.seed, "preliminary": preliminary,
                "needs_review": any(row["needs_review"] for row in rows),
                "sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [*sorted(CONFIG.glob('*.*')), *sorted((CONFIG / 'casos').glob('*.csv')),
                                        ROOT / 'correcciones/calificador_tarea_2.py',
                                        CONFIG / 'corregir.py', ROOT / 'scripts/traer-repos-trimestre.ps1',
                                        ROOT / 'correcciones/multicapa.py', ROOT / 'correcciones/multicapa_runner.py']},
                "evaluated_versions": [{"team": s.team, "file": s.file, "commit": s.commit,
                      "version": s.version, "source_dir": str(s.source_dir or '')} for s in all_versions]}
    (output / "ejecucion.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
