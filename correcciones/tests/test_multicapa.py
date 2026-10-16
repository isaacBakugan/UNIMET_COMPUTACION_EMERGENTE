"""Disk-discovered gates and grading regressions for Tarea 2."""
import csv
import json
from pathlib import Path

import pytest

from calificador import Submission, load_overrides, pick_best_versions
from calificador_tarea_2 import CONFIG, FILES, ROOT, ALLOWED_IMPORTS, build_submission, collect_submissions, prepare_data
from entregas import static_review
from multicapa import CASE_KEYS, load_profiles, network_metadata, score_trace, select_network
from rubrica import CaseResult, load_rubric, rubric_grade
from test_calificador import commit_on


def validate_dataset(path):
    dimensions = 2 if '2d_' in path.name else 3
    classes = 2 if dimensions == 2 else 4
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == [*(f'x{i}' for i in range(1, dimensions + 1)), 'y'], str(path)
        rows = list(reader)
    assert rows and len({float(row['y']) for row in rows}) == classes, str(path)
    assert all(len(row) == dimensions + 1 for row in rows), str(path)


def test_gate_discovers_complete_hidden_train_test_pairs():
    paths = sorted((CONFIG / 'casos').glob('*.csv'))
    assert paths, f'No hidden subjects found: {CONFIG / "casos"}'
    assert {p.name for p in paths} == {f'hidden_{d}d_{c}class_{split}.csv'
            for d, c in ((2, 2), (3, 4)) for split in ('train', 'test')}
    for path in paths:
        validate_dataset(path)
    for d, c in ((2, 2), (3, 4)):
        train = (CONFIG / 'casos' / f'hidden_{d}d_{c}class_train.csv').read_text().splitlines()[1:]
        test = (CONFIG / 'casos' / f'hidden_{d}d_{c}class_test.csv').read_text().splitlines()[1:]
        assert not set(train) & set(test), 'Hidden test must be held out'


def test_hidden_dataset_gate_reports_the_broken_subject(tmp_path):
    path = tmp_path / 'hidden_2d_2class_test.csv'
    path.write_text('wrong,y\n0,1\n')
    with pytest.raises(AssertionError, match=path.name):
        validate_dataset(path)


def test_gate_every_untouched_program_gets_minimum_grade():
    programs = sorted((ROOT / 'repo-template/tarea-2-codigo').glob('perceptron_multicapa_*.py'))
    assert programs, 'No template subjects discovered'
    assert {p.name for p in programs} == set(FILES)
    rubric = load_rubric(CONFIG / 'tarea.json')
    for path in programs:
        assert static_review(path.read_text(encoding='utf-8-sig'))['empty'], str(path)
        assert rubric_grade(rubric, dict.fromkeys(CASE_KEYS, 'no_result')) == (0, 1)


def test_real_submission_template_path_is_not_executed(tmp_path):
    import subprocess
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    folder = repo / 'tarea-2-codigo'
    folder.mkdir()
    for path in (ROOT / 'repo-template/tarea-2-codigo').glob('*.py'):
        (folder / path.name).write_text(path.read_text(encoding='utf-8-sig'))
    sha = commit_on(repo, 'initial', '2026-10-01T12:00:00-04:00')
    submission = build_submission('T', repo, FILES[0], sha, 0, 'cutoff', tmp_path / 'out', {}, [])
    assert submission.status == 'no_submission'


def test_plain_name_header_is_resolved_from_the_official_team_roster(tmp_path):
    import subprocess
    from calificador import load_delivery_list
    entries = load_delivery_list(ROOT / 'trimestre-actual/lista-entrega.csv')
    assert entries, 'No official roster subjects found'
    entry = entries[0]
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    folder = repo / 'tarea-2-codigo'
    folder.mkdir()
    (folder / FILES[0]).write_text(f'# {entry.full_name}\nx = 1\n', encoding='utf-8')
    sha = commit_on(repo, 'initial', '2026-10-01T12:00:00-04:00')
    submission = build_submission(entry.team, repo, FILES[0], sha, 0, 'cutoff', tmp_path / 'out', {}, [])
    assert submission.student_name == entry.full_name
    assert submission.national_id == ''


@pytest.mark.parametrize('matrix,outcome', [([[3, 0], [0, 5]], 'correct'), ([[2, 1], [1, 4]], 'incorrect'),
                                          ([[1, 0], [0, 1]], 'no_result'), ([[0, 0], [0, 0]], 'no_result')])
def test_confusion_matrix_needs_full_coverage(matrix, outcome):
    assert score_trace({'test_matrices': [matrix]}, [3, 5], 'ok').outcome == outcome


def test_timeout_and_training_only_evidence_cannot_receive_full_credit():
    assert score_trace({}, [3, 5], 'timeout').outcome == 'no_result'
    assert score_trace({'train_matrices': [[[3, 0], [0, 5]]]}, [3, 5], 'ok').outcome == 'no_result'


def test_menu_failure_after_complete_classification_does_not_erase_the_result():
    result = score_trace({'test_matrices': [[[3, 0], [0, 5]]], 'error': 'EOFError: extra menu'}, [3, 5], 'error_1')
    assert result.outcome == 'correct' and result.needs_review


def test_label_order_may_differ_from_sorted_dataset_labels():
    assert score_trace({'test_matrices': [[[5, 0], [0, 3]]]}, [3, 5], 'ok').outcome == 'correct'


def test_complete_explicit_comparison_is_evidence_even_when_the_matrix_omits_a_class():
    trace = {'test_matrices': [[[5, 0], [0, 0]]], 'test_comparisons': [
        {'title': 'Correctas / incorrectas', 'points': 8, 'colors': {'#228b22': 5, '#b22222': 3}}]}
    assert score_trace(trace, [3, 5], 'ok').outcome == 'incorrect'
    trace['test_comparisons'][0]['points'] = 5
    assert score_trace(trace, [3, 5], 'ok').outcome == 'no_result'


def test_pending_capture_does_not_publish_a_minimum_grade():
    from calificador import build_rows
    from calificador_tarea_2 import mark_pending_grades
    from lista import HEADER
    rubric = load_rubric(CONFIG / 'tarea.json')
    submission = Submission('T', 'R', FILES[0], assignment=HEADER)
    submission.cases = {key: CaseResult('no_result', 'Missing evidence', True) for key in CASE_KEYS}
    row = mark_pending_grades(build_rows([submission], rubric), [submission], rubric)[0]
    assert row['final_grade'] == '' and row['rubric_grade'] == ''
    assert row[CASE_KEYS[0]] == '' and row['grade_status'] == 'pending_evaluation'


def test_verified_empty_file_gets_minimum_only_with_verified_identity():
    from calificador import build_rows
    from calificador_tarea_2 import mark_pending_grades
    from lista import HEADER, BY_TEAM
    rubric = load_rubric(CONFIG / 'tarea.json')
    submission = Submission('T', 'R', FILES[0], assignment=HEADER, status='no_submission')
    submission.cases = {key: CaseResult('no_result', 'Empty template', False) for key in CASE_KEYS}
    assert mark_pending_grades(build_rows([submission], rubric), [submission], rubric)[0]['final_grade'] == 1
    submission.assignment = BY_TEAM
    row = mark_pending_grades(build_rows([submission], rubric), [submission], rubric)[0]
    assert row['final_grade'] == '' and row['rubric_grade'] == ''


def test_unique_name_networks_are_discovered_without_imposing_a_filename(tmp_path):
    path = tmp_path / 'red_2-d_2-class_Ana.csv'
    path.write_text('type,layer,index,w0,w1\nu,2,,,\nv,2,,,\nL,1,,,\nb,2,,,\ne,10,,,\nh,1,0,1,1\n')
    assert select_network(tmp_path, FILES[0], 2, 2, student_name='Ana Perez')[0] == path
    (tmp_path / FILES[1]).write_text('# Nombre: Ana Ruiz\nx=1\n')
    with pytest.raises(ValueError, match='Missing individual network'):
        select_network(tmp_path, FILES[0], 2, 2, student_name='Ana Perez')


def test_tarea_2_late_version_uses_its_own_criteria():
    rubric = load_rubric(CONFIG / 'tarea.json')
    cutoff = Submission('T', 'R', FILES[0])
    late = Submission('T', 'R', FILES[0], penalty=2, version='late', late_commits=['2026-10-11'])
    cutoff.cases = {key: CaseResult('incorrect', 'x') for key in CASE_KEYS}
    late.cases = {key: CaseResult('correct', 'x') for key in CASE_KEYS}
    assert pick_best_versions([cutoff, late], rubric, []) == [late]
    cutoff.cases = late.cases.copy()
    assert pick_best_versions([cutoff, late], rubric, []) == [cutoff]


def test_network_metadata_never_guesses_another_students_file(tmp_path):
    path = tmp_path / 'red_2d_2clases_1.csv'
    path.write_text('type,layer,index,w0,w1\nu,2,,,\nv,2,,,\nL,1,,,\nb,2,,,\ne,10,,,\nh,1,0,1,1\n')
    assert network_metadata(path)['e'] == 10
    assert select_network(tmp_path, FILES[0], 2, 2)[0] == path
    with pytest.raises(ValueError, match='Missing individual network'):
        select_network(tmp_path, FILES[1], 2, 2)
    with pytest.raises(ValueError):
        select_network(tmp_path, FILES[0], 2, 2, '../outside.csv')


def test_forbidden_frameworks_and_authorized_matrix_libraries():
    review = static_review('import numpy, pandas, matplotlib, csv\nimport torch, tensorflow, sklearn\n', ALLOWED_IMPORTS)
    assert review['forbidden_imports'] == ['sklearn', 'tensorflow', 'torch']


def test_profiles_and_teacher_decisions_are_commit_pinned(tmp_path):
    load_profiles(CONFIG / 'perfiles-consola.json')
    path = tmp_path / 'decision.json'
    path.write_text(json.dumps([{'team': 'T', 'file': FILES[0], 'commit': 'abc', 'reason': 'verified',
                         'cases': {CASE_KEYS[0]: {'outcome': 'correct', 'explanation': 'verified'}}}]))
    assert load_overrides(path, CASE_KEYS)[0]['commit'] == 'abc'
    with pytest.raises(ValueError):
        load_overrides(path)


def test_prepare_data_copies_all_authoritative_cases(tmp_path):
    data = prepare_data(tmp_path)
    assert len(list(data.glob('*.csv'))) == 8


def test_task_folder_entry_point_supports_the_grading_options():
    import subprocess
    import sys
    subjects = sorted(CONFIG.glob('corregir.py'))
    assert subjects, f'No Tarea 2 entry point found: {CONFIG / "corregir.py"}'
    for script in subjects:
        result = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True)
        assert result.returncode == 0, f'{script}: {result.stderr}'
        assert all(option in result.stdout for option in ('--update', '--clones', '--team', '--cutoff'))


def test_update_delegates_to_the_official_script_and_quotes_arguments(monkeypatch, tmp_path):
    import calificador_tarea_2 as grader
    calls = []
    monkeypatch.setattr(grader.shutil, 'which', lambda name: '/runtime/pwsh')
    monkeypatch.setattr(grader.subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    grader.refresh_clones(tmp_path / "clones' with spaces", ['T1', "T'2"], ('grupo-control',))
    args, options = calls[0]
    assert args[:4] == ['/runtime/pwsh', '-NoProfile', '-NonInteractive', '-Command']
    assert "traer-repos-trimestre.ps1'" in args[-1]
    assert "-Team @('T1','T''2')" in args[-1]
    assert "clones'' with spaces'" in args[-1]
    assert options == {'check': True}


def test_failed_official_refresh_aborts_before_collecting_or_writing_grades(monkeypatch, tmp_path):
    import calificador_tarea_2 as grader
    import subprocess
    import sys
    output = tmp_path / 'report'
    monkeypatch.setattr(sys, 'argv', ['corregir.py', '--update', '--output', str(output)])

    def failed_refresh(*args):
        raise subprocess.CalledProcessError(1, 'traer-repos-trimestre.ps1')

    def should_not_collect(*args):
        pytest.fail('Collected submissions after the official refresh failed')

    monkeypatch.setattr(grader, 'refresh_clones', failed_refresh)
    monkeypatch.setattr(grader, 'collect_submissions', should_not_collect)
    with pytest.raises(subprocess.CalledProcessError):
        grader.main()
    assert not output.exists()


def test_future_sentinel_does_not_wrap_to_the_past_in_git(tmp_path):
    import subprocess
    from entregas import commit_at_cutoff, commits_after_cutoff
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    sha = commit_on(tmp_path, 'initial', '2026-10-01T12:00:00-04:00')
    assert commit_at_cutoff(tmp_path, '2099-12-31T23:59:00-04:00') == sha
    assert commits_after_cutoff(tmp_path, '2099-12-31T23:59:00-04:00') == []


def test_commit_at_the_last_second_is_on_time(tmp_path):
    import subprocess
    from entregas import commit_at_cutoff, commits_after_cutoff
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    cutoff = '2026-10-11T23:59:59-04:00'
    sha = commit_on(tmp_path, 'exact', cutoff)
    assert commit_at_cutoff(tmp_path, cutoff) == sha
    assert commits_after_cutoff(tmp_path, cutoff) == []


def test_a_weights_only_late_update_triggers_the_individual_policy(tmp_path):
    import subprocess
    from dataclasses import replace
    repo = tmp_path / 'R'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    folder = repo / 'tarea-2-codigo'
    folder.mkdir()
    (folder / FILES[0]).write_text('# Nombre: Test\nx = 1\n')
    path = folder / 'red_2d_2clases_1.csv'
    path.write_text('initial')
    on_time = commit_on(repo, 'on time', '2026-10-11T12:00:00-04:00')
    path.write_text('changed')
    late_sha = commit_on(repo, 'weights only', '2026-10-12T12:00:00-04:00')
    # Simulate fetch advancing origin while the local checkout remains on the older commit.
    subprocess.run(['git', '-C', str(repo), 'update-ref', 'refs/remotes/origin/main', late_sha], check=True)
    subprocess.run(['git', '-C', str(repo), 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main'], check=True)
    local_branch = subprocess.check_output(['git', '-C', str(repo), 'symbolic-ref', 'HEAD'], text=True).strip()
    subprocess.run(['git', '-C', str(repo), 'update-ref', local_branch, on_time], check=True)
    rubric = replace(load_rubric(CONFIG / 'tarea.json'), cutoff='2026-10-11T23:59:59-04:00')
    submissions = collect_submissions([('T', 'R')], tmp_path, rubric, tmp_path / 'out', {}, {}, [])
    versions = [s for s in submissions if s.file == FILES[0]]
    assert [s.commit for s in versions] == [on_time, late_sha]
    assert [s.penalty for s in versions] == [0, 2]
    assert len([s for s in submissions if s.file == FILES[1]]) == 1


def test_nonperfect_classification_requires_judgment_instead_of_an_automatic_deduction():
    from calificador import build_rows
    from calificador_tarea_2 import mark_pending_grades
    from lista import HEADER
    rubric = load_rubric(CONFIG / 'tarea.json')
    submission = Submission('T', 'R', FILES[0], assignment=HEADER)
    submission.cases = {key: score_trace({'test_matrices': [[[3, 0], [0, 5]]]}, [3, 5], 'ok')
                        for key in CASE_KEYS}
    submission.cases[CASE_KEYS[0]] = score_trace({'test_matrices': [[[2, 1], [0, 5]]]}, [3, 5], 'ok')
    row = mark_pending_grades(build_rows([submission], rubric), [submission], rubric)[0]
    assert row['final_grade'] == '' and row[CASE_KEYS[0]] == ''
    assert row['pending_criteria'] == CASE_KEYS[0]


@pytest.mark.parametrize('changed', ['none', 'commit', 'trace', 'teacher'])
def test_visual_judgment_requires_the_exact_evidence_and_preserves_teacher_decisions(tmp_path, changed):
    import hashlib
    from calificador_tarea_2 import apply_visual_reviews
    submission = Submission('T', 'R', FILES[0], commit='abc')
    submission.evidence_path = 'evidence/test'
    case = CASE_KEYS[0]
    source = 'teacher_decision' if changed == 'teacher' else 'classification_review_required'
    submission.cases = {case: CaseResult('incorrect', 'original', True, source)}
    path = tmp_path / submission.evidence_path / case / 'traza.json'
    path.parent.mkdir(parents=True)
    path.write_text('{}')
    review = {'team': 'T', 'file': FILES[0], 'commit': 'other' if changed == 'commit' else 'abc',
              'reason': 'Pattern inspected', 'cases': {case: {'outcome': 'correct',
                'explanation': 'Boundary errors with learned class separation',
                'trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}}
    if changed == 'trace':
        path.write_text('{"changed": true}')
    warnings = []
    apply_visual_reviews([submission], [review], tmp_path, warnings)
    result = submission.cases[case]
    assert result.outcome == ('correct' if changed == 'none' else 'incorrect')
    assert result.needs_review
    if changed == 'none':
        assert result.source == 'visual_review'
    if changed in ('commit', 'trace'):
        assert warnings


def test_code_delivery_is_distinct_from_missing_trained_networks():
    from calificador import build_rows
    from calificador_tarea_2 import mark_pending_grades
    from lista import HEADER
    rubric = load_rubric(CONFIG / 'tarea.json')
    submission = Submission('T', 'R', FILES[0], assignment=HEADER)
    submission.cases = {key: CaseResult('no_result', 'Missing trained file', True, 'missing_network') for key in CASE_KEYS}
    row = mark_pending_grades(build_rows([submission], rubric), [submission], rubric)[0]
    assert row['delivery_status'] == 'code_delivered_missing_networks'
    assert row['final_grade'] == ''
    assert row['comment'].startswith('Código entregado;')


def test_private_identity_confirmation_is_loaded_without_changing_the_public_roster(tmp_path):
    from calificador_tarea_2 import load_identities
    public = tmp_path / 'public.csv'
    private = tmp_path / 'private.csv'
    public.write_text('team,file,student_name,national_id\nT,a.py,,\n', encoding='utf-8')
    private.write_text('team,file,student_name,national_id\nT,a.py,Ana Perez,\n', encoding='utf-8')
    assert load_identities(public, private)['T','a.py']['student_name'] == 'Ana Perez'
    assert 'Ana' not in public.read_text()
    private.write_text('team,file,student_name,national_id\nOther,a.py,Ana Perez,\n', encoding='utf-8')
    with pytest.raises(ValueError):
        load_identities(public, private)


def test_functional_diagnostics_never_replace_missing_rubric_results(tmp_path, monkeypatch):
    import calificador_tarea_2 as grader
    submission = Submission('T', 'R', FILES[0], student_name='Ana Perez')
    submission.evidence_path = 'evidence/T/a/abc'
    submission.cases = {key: CaseResult('no_result', 'Missing file', True, 'missing_network') for key in CASE_KEYS}
    original = submission.cases.copy()
    calls = []
    def observed(*args, **kwargs):
        calls.append((args, kwargs))
        return CaseResult('correct', 'All diagnostic samples classified', True)
    monkeypatch.setattr(grader, 'run_case', observed)
    records = grader.check_delivered_code([submission], tmp_path, tmp_path, 120, 2526)
    assert len(records) == 2 and all(r['diagnostic_only'] for r in records)
    assert submission.cases == original and submission.evidence_path.startswith('evidence/')
    assert all(k['diagnostic'] for a, k in calls)
    assert all(a[0].evidence_path.startswith('code-checks/') for a, k in calls)


def test_a_late_syntax_error_is_delivered_code_not_the_empty_cutoff_template():
    from calificador_tarea_2 import retain_incomplete_late_code
    cutoff = Submission('T', 'R', FILES[0], status='no_submission')
    late = Submission('T', 'R', FILES[0], version='late', status='does_not_compile')
    cutoff.cases = {key: CaseResult('no_result', 'Empty', False) for key in CASE_KEYS}
    late.cases = {key: CaseResult('no_result', 'Syntax error', True) for key in CASE_KEYS}
    selected = [cutoff]
    retain_incomplete_late_code(selected, [cutoff, late])
    assert selected == [late]


def test_reports_show_delivered_code_separately_from_the_pending_grade(tmp_path):
    from calificador import build_rows, write_outputs
    from calificador_tarea_2 import mark_pending_grades
    from lista import HEADER
    rubric = load_rubric(CONFIG / 'tarea.json')
    submission = Submission('T', 'R', FILES[0], assignment=HEADER, student_name='Ana Perez')
    submission.cases = {key: CaseResult('no_result', 'Missing trained file', True, 'missing_network') for key in CASE_KEYS}
    rows = mark_pending_grades(build_rows([submission], rubric), [submission], rubric)
    write_outputs(rows, [submission], rubric, tmp_path, 'test', [])
    report = (tmp_path / 'informe.md').read_text(encoding='utf-8')
    assert 'Equipo / archivo | Entrega |' in report
    assert 'Código entregado; faltan redes CSV' in report and '**Pendiente**' in report
    sheet = list(csv.DictReader((tmp_path / 'notas-sheets.csv').open(encoding='utf-8-sig')))[0]
    assert sheet['Nota'] == '' and 'Código entregado;' in sheet['Observación']


@pytest.mark.parametrize('dataset,prefix', [('practice', '2-d_2-class'), ('hidden', 'hidden_2d_2class')])
def test_diagnostics_use_the_requested_train_and_test_without_borrowing_a_network(tmp_path, monkeypatch, dataset, prefix):
    import calificador_tarea_2 as grader
    from types import SimpleNamespace
    data = grader.prepare_data(tmp_path)
    submission = Submission('T', 'R', FILES[0], source_dir=tmp_path)
    submission.evidence_path = 'diagnostic/T'
    def forbidden_network_lookup(*args):
        pytest.fail('A diagnostic must create its own network')
    monkeypatch.setattr(grader, 'select_network', forbidden_network_lookup)
    monkeypatch.setattr(grader, 'isolated_command', lambda *args: ['sandbox'])
    monkeypatch.setattr(grader.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='', stderr=''))
    grader.run_case(submission, CASE_KEYS[2], data, tmp_path, 120, 2526, {}, diagnostic=True, diagnostic_data=dataset)
    job = json.loads((tmp_path / submission.evidence_path / CASE_KEYS[2] / 'job.json').read_text())
    assert job['test_csv'] == f'/data/{prefix}_test.csv'
    assert f'/data/{prefix}_train.csv' in job['answers']
    assert job['network'] == '' and job['diagnostic_only']
