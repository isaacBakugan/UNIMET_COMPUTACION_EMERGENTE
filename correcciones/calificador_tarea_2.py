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
from multicapa import CASE_KEYS, FILES, FOLDER, console_answers, load_profiles, score_trace, select_network, pending_cases
from lista import normalize, BY_TEAM, UNASSIGNED
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


def run_case(submission, case, data, output, timeout, seed, spec, diagnostic=False, diagnostic_data='hidden'):
    out = output / submission.evidence_path / case
    out.mkdir(parents=True, exist_ok=True)
    for stale in (*out.glob("grafico_*.png"), *(out / name for name in
                 ('traza.json', 'job.json', 'resultado.json', 'salida.txt', 'errores.txt'))):
        stale.unlink(missing_ok=True)
    def pending_result(explanation, source='automatic'):
        result = CaseResult('no_result', explanation, True, source)
        (out / 'resultado.json').write_text(json.dumps({'status': 'pending', 'outcome': result.outcome,
                'explanation': result.explanation, 'needs_review': True}, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    dimensions, classes = (2, 2) if "2d_2class" in case else (3, 4)
    if diagnostic:
        # Common diagnostic settings are never used as the student's rubric hyperparameters.
        metadata = {"u": dimensions, "v": classes, "L": 1, "b": 8, "e": 1000}
        network_path = ""
    else:
        try:
            network, metadata = select_network(submission.source_dir, submission.file, dimensions, classes,
                                               spec.get("network"), submission.student_name)
        except (ValueError, OSError) as exc:
            return pending_result("Código entregado; no se localizó la red CSV propia necesaria para este criterio. "
                                  + str(exc) + ". Esto no equivale a una ausencia de entrega del programa.", 'missing_network')
        network_path = "/src/" + network.relative_to(submission.source_dir.resolve()).as_posix()
    if case.startswith("hidden") and metadata["e"] == 0:
        return pending_result("La red entregada registra cero épocas; sus hiperparámetros no permiten este entrenamiento.")
    test_name = (f"{dimensions}-d_{classes}-class" if case.startswith("given")
                 else f"hidden_{dimensions}d_{classes}class") + "_test.csv"
    answers = spec.get("answers", console_answers(case, metadata, network_path))
    if diagnostic and diagnostic_data == 'practice':
        hidden_prefix = f"hidden_{dimensions}d_{classes}class"
        practice_prefix = f"{dimensions}-d_{classes}-class"
        test_name = practice_prefix + '_test.csv'
        answers = [answer.replace('/data/' + hidden_prefix, '/data/' + practice_prefix) for answer in answers]
    test_csv = "/data/" + test_name
    substitutions = {"{network}": network_path, "{test}": test_csv,
                     "{train}": f"/data/hidden_{dimensions}d_{classes}class_train.csv",
                     **{f"{{{key}}}": str(value) for key, value in metadata.items()}}
    answers = [substitutions.get(answer, answer) for answer in answers]
    if test_csv not in answers:
        raise ValueError(f"Console profile must include the test CSV: {submission.file}/{case}")
    job = {"answers": answers, "seed": seed, "metadata": metadata, "network": network_path,
           "test_csv": test_csv, "cpu_seconds": timeout, "diagnostic_only": diagnostic, "diagnostic_data": diagnostic_data if diagnostic else None}
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
    if diagnostic:
        result = replace(result, explanation=result.explanation.replace(
            'La rúbrica no exige 100 %; revisar el patrón de clasificación antes de decidir 25 o 15.',
            'Prueba funcional con una red creada durante el diagnóstico.'))
    (out / "resultado.json").write_text(json.dumps({"status": status, "outcome": result.outcome,
            "explanation": result.explanation, "needs_review": result.needs_review}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def mark_pending_grades(rows, submissions, rubric):
    """Do not publish a numerical grade for an unresolved test or a provisional identity."""
    for row, submission in zip(rows, submissions):
        pending = pending_cases(submission)
        provisional = submission.assignment in (BY_TEAM, UNASSIGNED)
        row['grade_status'] = 'pending_evaluation' if pending else ('pending_identity' if provisional else 'proposed')
        row['pending_criteria'] = ', '.join(pending)
        missing_networks = any(result.source == 'missing_network' for result in submission.cases.values())
        if submission.status == 'no_submission':
            row['delivery_status'] = 'empty_or_missing_code'
            row['delivery_note'] = 'Archivo vacío, solo plantilla/comentarios o ausente.'
        elif submission.status == 'does_not_compile':
            row['delivery_status'] = 'code_delivered_syntax_error'
            row['delivery_note'] = 'Código entregado; contiene un error de sintaxis: ' + ' '.join(submission.notes[:1])
        elif missing_networks:
            row['delivery_status'] = 'code_delivered_missing_networks'
            row['delivery_note'] = 'Código entregado; faltan las redes CSV propias necesarias para calcular los cuatro criterios.'
        else:
            row['delivery_status'] = 'code_delivered'
            row['delivery_note'] = 'Código entregado.'
        if pending or provisional:
            row['final_grade'] = ''
            row['rubric_grade'] = ''
            row['rubric_points'] = ''
        if pending:
            for case in pending:
                row[case] = ''
            row['comment'] = ' '.join(
                f"{rubric.description(case)} ({'pendiente' if case in pending else str(row[case]) + '/25'}): "
                f"{submission.cases[case].explanation}" for case in CASE_KEYS) + ' ' + ' '.join(submission.notes)
        row['comment'] = row['delivery_note'] + ' ' + row['comment']
    return rows


def retain_incomplete_late_code(submissions, all_versions):
    """Keep delivered late code visible even if it cannot compile or lacks evidence."""
    # A tie at the minimum cannot hide a late program behind an untouched cutoff template.
    # Keep the late evidence for review, without assigning it a numeric grade.
    for index, chosen in enumerate(submissions):
        if chosen.status != 'no_submission':
            continue
        later = next((s for s in all_versions if (s.team, s.file) == (chosen.team, chosen.file)
                      and s.version == 'late' and s.status != 'no_submission' and pending_cases(s)), None)
        if later is not None:
            later.notes.append('Hay código entregado después del cierre; la evaluación sigue pendiente. '
                               'No se considera una ausencia de entrega ni se publica la mínima por falta de evidencia.')
            submissions[index] = later


def load_identities(public_path, confirmed_path):
    """Merge private confirmations without publishing identities in the grader configuration."""
    rows = read_csv(public_path)
    indexed = {(row['team'], row['file']): row for row in rows}
    if confirmed_path.is_file():
        confirmed = read_csv(confirmed_path)
        seen = set()
        for row in confirmed:
            key = row['team'], row['file']
            if key not in indexed or key in seen or not row['student_name'].strip():
                raise ValueError(f'Invalid confirmed identity: {key}')
            indexed[key] = {**indexed[key], **row}
            seen.add(key)
    return indexed


def check_delivered_code(submissions, data, output, timeout, seed, dataset='practice'):
    """Run independent functional diagnostics without modifying any rubric outcome."""
    dataset_description = 'los datos de práctica de assets/' if dataset == 'practice' else 'los datasets no vistos de corrección'
    report_stem = 'comprobacion_codigo_practica' if dataset == 'practice' else 'comprobacion_codigo'
    lines = ['# Comprobación funcional del código entregado', '',
             'Diagnóstico separado de las notas. Se crea una red con L=1, b=8 y 1000 épocas, '
             f'con {dataset_description}. Estos parámetros son del diagnóstico, '
             'no entregados por el estudiante: los resultados no completan ni sustituyen los cuatro criterios.', '',
             '| Estudiante | Equipo / archivo | Caso | Resultado observado |', '|---|---|---|---|']
    records = []
    for submission in submissions:
        if submission.status != 'graded' or not any(r.source == 'missing_network' for r in submission.cases.values()):
            continue
        diagnostic = replace(submission)
        diagnostic.evidence_path = submission.evidence_path.replace('evidence/', f'code-checks/{dataset}/', 1)
        for case in CASE_KEYS[2:]:
            print(f'Checking code {submission.team}/{submission.file}: {case}', flush=True)
            result = run_case(diagnostic, case, data, output, timeout, seed, {}, diagnostic=True, diagnostic_data=dataset)
            status_path = output / diagnostic.evidence_path / case / 'resultado.json'
            execution_status = json.loads(status_path.read_text(encoding='utf-8'))['status'] if status_path.exists() else 'unknown'
            display_case = '2D / 2 clases' if '2d_2class' in case else '3D / 4 clases'
            lines.append(f'| {submission.student_name} | {submission.team}/{submission.file} | {display_case} | Ejecución: {execution_status}. {result.explanation} |')
            records.append({'team': submission.team, 'file': submission.file, 'commit': submission.commit,
                            'case': case, 'dataset': dataset, 'diagnostic_only': True, 'execution_status': execution_status, 'observed': result.outcome,
                            'explanation': result.explanation, 'evidence': diagnostic.evidence_path})
    (output / (report_stem + '.md')).write_text('\n'.join(lines), encoding='utf-8')
    (output / (report_stem + '.json')).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


def apply_visual_reviews(submissions, reviews, output, warnings):
    """Apply private proposed visual judgments only to the exact commit and trace inspected."""
    indexed = {(s.team, s.file, s.commit): s for s in submissions}
    for item in reviews:
        key = (item['team'], item['file'], item['commit'])
        submission = indexed.get(key)
        if submission is None:
            if any(s.team == item['team'] for s in submissions):
                warnings.append(f"Revisión visual obsoleta: {key}; no se aplicó.")
            continue
        applied = False
        for case, decision in item['cases'].items():
            if submission.cases[case].source == 'teacher_decision':
                continue
            path = output / submission.evidence_path / case / 'traza.json'
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != decision.get('trace_sha256'):
                warnings.append(f"Revisión visual pendiente de renovar: {submission.team}/{submission.file}/{case}; cambió la evidencia.")
                continue
            submission.cases[case] = CaseResult(decision['outcome'], decision['explanation'], True, 'visual_review')
            applied = True
        if applied:
            submission.notes.append('Revisión visual propuesta: ' + item['reason'] + ' Pendiente de validación docente.')


def write_delivery_audit(rows, submissions, output):
    """Explain what was actually delivered, independently of the numerical rubric outcome."""
    lines = ['# Auditoría de entregas de la Tarea 2', '',
             'Una nota pendiente no significa que no hubo entrega. Las identidades por equipo son provisionales.', '',
             '| Estudiante | Equipo / archivo | Versión | Código | Redes CSV propias usadas | Nota propuesta | Estado |',
             '|---|---|---|---|---|---|---|']
    for row, submission in zip(rows, submissions):
        path = submission.source_dir / submission.file if submission.source_dir else None
        source = path.read_text(encoding='utf-8-sig', errors='replace') if path and path.is_file() else ''
        code = ('Plantilla vacía' if static_review(source, ALLOWED_IMPORTS)['empty'] else
                f"Código presente ({len(source.splitlines())} líneas)") if source else 'Archivo ausente'
        networks = set()
        for job in (output / submission.evidence_path).glob('*/job.json'):
            data = json.loads(job.read_text(encoding='utf-8'))
            networks.add(data['network'].removeprefix('/src/'))
        status = {'pending_evaluation': row['delivery_note'] + ' Evaluación incompleta.',
                  'pending_identity': 'Archivo vacío; identidad sin confirmar',
                  'proposed': 'Nota propuesta; revisar criterios visuales'}[row['grade_status']]
        if row['assignment'] in (BY_TEAM, UNASSIGNED):
            status += '; identidad provisional'
        who = f"{row['last_name']}, {row['first_name']}"
        lines.append(f"| {who} | {submission.team}/{submission.file} | {submission.version} `{submission.commit[:10]}` | "
                     f"{code} | {', '.join(sorted(networks)) or 'No se localizó una red propia evaluable'} | "
                     f"{row['final_grade'] if row['final_grade'] != '' else 'Pendiente'} | {status} |")
    lines += ['', 'Las filas con código y sin redes no son una ausencia de entrega: falta un entregable de la rúbrica. '
              'No se sustituyen sus pesos ni sus hiperparámetros por los de otro integrante.', '',
              'Los puntajes 25/15 mantienen su condición de propuesta: la rúbrica no fija un umbral de accuracy; '
              'la revisión docente puede aceptar una separación correcta con errores sin que el script invente un umbral.']
    (output / 'auditoria_entregas.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Run scripts/traer-repos-trimestre.ps1 before grading")
    parser.add_argument("--team", action="append")
    parser.add_argument("--clones", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cutoff")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--seed", type=int, default=2526)
    parser.add_argument('--visual-reviews', type=Path, default=CONFIG / 'revision-visual.local.json',
                        help='Private proposed visual judgments pinned to a commit and trace hash')
    parser.add_argument('--identities', type=Path, default=CONFIG / 'identidades-confirmadas.local.csv',
                        help='Private identity confirmations from the preparer')
    parser.add_argument('--check-code', action='store_true',
                        help='Run non-grading functional diagnostics for programs missing their trained CSVs')
    parser.add_argument('--diagnostic-data', choices=('practice', 'hidden'), default='practice',
                        help='Datasets for non-grading code checks (default: practice assets)')
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
    roster = load_identities(CONFIG / "alumnos.csv", args.identities)
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
                submission.cases[case] = CaseResult("no_result", " ".join(submission.notes), submission.status != 'no_submission')
            else:
                print(f"Running {submission.team}/{submission.file}@{submission.commit[:10]}: {case}", flush=True)
                spec = dict(profile["cases"].get(case, {}))
                network = networks.get((submission.team, submission.file), {}).get("2d" if "2d_" in case else "3d")
                if network and "network" not in spec:
                    spec["network"] = network
                submission.cases[case] = run_case(submission, case, data, output, args.timeout,
                                                   args.seed, spec)
    if args.visual_reviews.is_file():
        apply_visual_reviews(submissions, load_overrides(args.visual_reviews, CASE_KEYS), output, warnings)
    all_versions = list(submissions)
    submissions = pick_best_versions(submissions, rubric, warnings)
    retain_incomplete_late_code(submissions, all_versions)
    for chosen in submissions:
        unresolved = [s for s in all_versions if (s.team, s.file) == (chosen.team, chosen.file)
                      and any(result.needs_review for result in s.cases.values())]
        if unresolved:
            chosen.notes.append("Nota propuesta: hay evidencia o versiones pendientes de revisión docente.")
            for key in CASE_KEYS:
                chosen.cases[key].needs_review |= any(s.cases[key].needs_review for s in unresolved)
    submissions = order_by_delivery_list(submissions,
                   load_delivery_list(ROOT / "trimestre-actual" / "lista-entrega.csv"), warnings)
    rows = mark_pending_grades(build_rows(submissions, rubric), submissions, rubric)
    write_outputs(rows, submissions, rubric, output, term, warnings, preliminary)
    write_delivery_audit(rows, submissions, output)
    diagnostics = check_delivered_code(submissions, data, output, args.timeout, args.seed, args.diagnostic_data) if args.check_code else []
    if args.check_code:
        with (output / 'informe.md').open('a', encoding='utf-8') as stream:
            stream.write('\n\n## Comprobación del código entregado\n\n'
                         f"[Diagnóstico funcional separado]({'comprobacion_codigo_practica.md' if args.diagnostic_data == 'practice' else 'comprobacion_codigo.md'}). No sustituye las redes CSV entregables ni modifica las notas.\n")
    print_summary(rows, output, CASE_KEYS)
    for message in warnings:
        print("ADVERTENCIA: " + message)
    manifest = {"central_commit": git(ROOT, "rev-parse", "HEAD"), "cutoff": rubric.cutoff,
                "seed": args.seed, "preliminary": preliminary, "code_checks": len(diagnostics),
                "confirmed_identities_sha256": hashlib.sha256(args.identities.read_bytes()).hexdigest() if args.identities.is_file() else None,
                "visual_reviews_sha256": hashlib.sha256(args.visual_reviews.read_bytes()).hexdigest() if args.visual_reviews.is_file() else None,
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
