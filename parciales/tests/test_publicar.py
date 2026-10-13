"""Tests of the single-project publication (parciales/publicar.py) and its gates."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

import formulario
import publicar

ROOT = Path(__file__).resolve().parent.parent.parent
APPS_SCRIPT = ROOT / "parciales" / "apps-script"


def make_bank_question(index, section="simple_choice"):
    options = ([{"text": "Verdadero", "correct": True}, {"text": "Falso", "correct": False}]
               if section == "true_false" else [{"text": "a", "correct": False}, {"text": "b", "correct": True}])
    return {"id": f"q{index:03d}", "name": f"Pregunta {index}", "section": section, "category": "X", "family": f"x|{index}",
            "stem": f"enunciado {index}", "shuffle_options": False, "image_files": [], "review_flags": [], "options": options}


BANK = {"questions": [make_bank_question(1, "true_false"), make_bank_question(2), make_bank_question(3)]}


def write_resolved(specs_dir, name, ids):
    sections = [{"title": "VF", "section": "true_false", "points": 1, "questions": [{"id": ids[0], "name": "x"}]},
                {"title": "SS", "section": "simple_choice", "points": 1, "questions": [{"id": i, "name": "x"} for i in ids[1:]]}]
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / f"{name}.resuelto.local.json").write_text(
        json.dumps({"title": name, "mode": "practice", "sections": sections}), encoding="utf-8")


def write_config(tmp_path, data):
    path = tmp_path / "publicacion.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def build(tmp_path, exam):
    return publicar.build_payload(exam, BANK, tmp_path / "specs", tmp_path / "banco.json")


def project(tmp_path, monkeypatch):
    """A fake apps-script folder plus the specs and bank it reads from."""
    apps = tmp_path / "apps-script"
    apps.mkdir()
    (tmp_path / "banco.json").write_text(json.dumps(BANK), encoding="utf-8")
    monkeypatch.setattr(publicar, "APPS_SCRIPT_DIR", apps)
    monkeypatch.setattr(publicar, "SPECS_DIR", tmp_path / "specs")
    return apps


def test_names_are_derived_from_the_target():
    assert publicar.data_file("practice") == "ExamDataPractice.gs"
    assert publicar.constant_name("practice") == "EXAM_PRACTICE"
    assert publicar.function_name("practice") == "createExamPractice"
    assert publicar.data_file("real-2") == "ExamDataReal2.gs"
    assert publicar.constant_name("real-2") == "EXAM_REAL_2" and publicar.function_name("real-2") == "createExamReal2"


def test_the_config_maps_each_target_to_a_resolved_exam_and_skips_comments(tmp_path):
    path = write_config(tmp_path, {"_ayuda": "x", "practice": "real-1-practica", "real": "parcial-1-real"})
    assert publicar.load_config(path) == {"practice": "real-1-practica", "real": "parcial-1-real"}


@pytest.mark.parametrize("data, message", [
    ({"_ayuda": "solo comentarios"}, "no targets"),
    ({"Practice": "a"}, "lowercase"),
    ({"practice": ""}, "must name a resolved exam"),
    ({"practice": 3}, "must name a resolved exam"),
    ({"practice": "mismo", "real": "mismo"}, "more than one target"),
])
def test_a_config_that_would_publish_the_wrong_exam_is_rejected(tmp_path, data, message):
    with pytest.raises(publicar.PublishError, match=message):
        publicar.load_config(write_config(tmp_path, data))


def test_staging_writes_one_data_file_per_target_with_its_own_constant(tmp_path):
    apps = tmp_path / "apps-script"
    apps.mkdir()
    write_resolved(tmp_path / "specs", "uno", ["q001", "q002"])
    write_resolved(tmp_path / "specs", "dos", ["q001", "q003"])
    payloads = {"practice": build(tmp_path, "uno"), "real": build(tmp_path, "dos")}
    written = publicar.stage(payloads, apps)
    assert [p.name for p in written] == ["ExamDataPractice.gs", "ExamDataReal.gs"]
    practice, real = (p.read_text(encoding="utf-8") for p in written)
    assert practice == formulario.render(payloads["practice"], "EXAM_PRACTICE")
    assert practice.startswith("// Generated") and "const EXAM_PRACTICE = " in practice and "const EXAM_REAL" in real
    assert "enunciado 3" in real and "enunciado 3" not in practice


def test_swapping_the_exam_of_a_target_replaces_only_its_data_file(tmp_path):
    apps = tmp_path / "apps-script"
    apps.mkdir()
    write_resolved(tmp_path / "specs", "uno", ["q001", "q002"])
    write_resolved(tmp_path / "specs", "dos", ["q001", "q003"])
    publicar.stage({"practice": build(tmp_path, "uno"), "real": build(tmp_path, "dos")}, apps)
    before = (apps / "ExamDataReal.gs").read_text(encoding="utf-8")
    publicar.stage({"practice": build(tmp_path, "dos"), "real": build(tmp_path, "dos")}, apps)
    assert "enunciado 3" in (apps / "ExamDataPractice.gs").read_text(encoding="utf-8")
    assert (apps / "ExamDataReal.gs").read_text(encoding="utf-8") == before


def test_a_data_file_of_a_target_that_no_longer_exists_is_deleted(tmp_path):
    """A stale ExamData*.gs would be pushed with the folder and keep defining a global."""
    apps = tmp_path / "apps-script"
    apps.mkdir()
    (apps / "ExamDataViejo.gs").write_text("const EXAM_VIEJO = {};", encoding="utf-8")
    (apps / "Code.gs").write_text("// code", encoding="utf-8")
    write_resolved(tmp_path / "specs", "uno", ["q001", "q002"])
    publicar.stage({"practice": build(tmp_path, "uno")}, apps)
    assert sorted(p.name for p in apps.iterdir()) == ["Code.gs", "ExamDataPractice.gs"]


def test_a_missing_resolved_exam_says_which_command_creates_it(tmp_path):
    with pytest.raises(publicar.PublishError, match=r"armar\.py .*examen-que-no-existe\.local\.json"):
        publicar.build_payload("examen-que-no-existe", BANK, tmp_path, tmp_path / "banco.json")


def test_one_broken_target_leaves_the_project_untouched(tmp_path, monkeypatch, capsys):
    apps = project(tmp_path, monkeypatch)
    write_resolved(tmp_path / "specs", "bueno", ["q001", "q002"])    # "roto" is never resolved
    config = write_config(tmp_path, {"practice": "bueno", "real": "roto"})
    assert publicar.main(["--config", str(config), "--bank", str(tmp_path / "banco.json")]) == 1
    assert "roto.resuelto.local.json not found" in capsys.readouterr().out
    assert list(apps.iterdir()) == []


def test_main_stages_every_target_and_names_the_function_to_run(tmp_path, monkeypatch, capsys):
    apps = project(tmp_path, monkeypatch)
    write_resolved(tmp_path / "specs", "bueno", ["q001", "q002"])
    write_resolved(tmp_path / "specs", "otro", ["q001", "q003"])
    config = write_config(tmp_path, {"practice": "bueno", "real": "otro"})
    assert publicar.main(["--config", str(config), "--bank", str(tmp_path / "banco.json")]) == 0
    assert sorted(p.name for p in apps.iterdir()) == ["ExamDataPractice.gs", "ExamDataReal.gs"]
    out = capsys.readouterr().out
    assert "createExamPractice()" in out and "createExamReal()" in out and "Staged only" in out


def test_main_pushes_once_for_the_whole_project(tmp_path, monkeypatch):
    apps = project(tmp_path, monkeypatch)
    write_resolved(tmp_path / "specs", "bueno", ["q001", "q002"])
    write_resolved(tmp_path / "specs", "otro", ["q001", "q003"])
    config = write_config(tmp_path, {"practice": "bueno", "real": "otro"})
    pushed = []
    monkeypatch.setattr(publicar, "push", lambda folder: pushed.append(folder))
    assert publicar.main(["--config", str(config), "--bank", str(tmp_path / "banco.json"), "--push"]) == 0
    assert pushed == [apps]


def test_push_needs_clasp_and_a_linked_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar.shutil, "which", lambda name: None)
    with pytest.raises(publicar.PublishError, match="not on the PATH"):
        publicar.push(tmp_path)
    monkeypatch.setattr(publicar.shutil, "which", lambda name: "clasp")
    with pytest.raises(publicar.PublishError, match="clasp create"):    # the message carries the one-time command
        publicar.push(tmp_path)


def test_push_runs_clasp_from_the_project_folder_and_surfaces_a_failure(tmp_path, monkeypatch):
    (tmp_path / ".clasp.json").write_text("{}", encoding="utf-8")
    calls = []

    def fake_run(command, cwd):
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0 if len(calls) == 1 else 1)

    monkeypatch.setattr(publicar.shutil, "which", lambda name: "clasp")
    monkeypatch.setattr(publicar.subprocess, "run", fake_run)
    publicar.push(tmp_path)
    assert calls == [(["clasp", "push", "--force"], tmp_path)]
    with pytest.raises(publicar.PublishError, match="previous exam data"):
        publicar.push(tmp_path)


# --- gates: discovered from the config and from Code.gs, never from a list somebody remembered to extend ---

def test_gate_the_real_config_is_valid_and_declares_both_exams():
    assert {"practice", "real"} <= set(publicar.load_config())    # a gate that finds nothing passes green and proves nothing


def test_gate_every_target_has_its_function_in_code_gs_and_every_function_has_its_target():
    code = (APPS_SCRIPT / "Code.gs").read_text(encoding="utf-8")
    targets = publicar.load_config()
    for target in targets:
        assert re.search(rf"function {publicar.function_name(target)}\(\)\s*\{{\s*return buildExam_\({publicar.constant_name(target)}, false\)", code), \
            f"Code.gs has no {publicar.function_name(target)}() calling buildExam_({publicar.constant_name(target)}, false)"
        assert re.search(rf"function {publicar.function_name(target)}Again\(\)\s*\{{\s*return buildExam_\({publicar.constant_name(target)}, true\)", code), \
            f"Code.gs has no {publicar.function_name(target)}Again()"
    declared = set(re.findall(r"function (createExam\w+?)(?:Again)?\(\)", code))
    expected = {publicar.function_name(target) for target in targets}
    assert declared == expected, f"Code.gs functions {sorted(declared)} do not match the targets {sorted(expected)}"


def test_gate_only_the_shared_source_of_apps_script_is_versioned():
    tracked = subprocess.run(["git", "ls-files", "parciales/apps-script"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split()
    assert sorted(tracked) == ["parciales/apps-script/Code.gs", "parciales/apps-script/appsscript.json"], \
        "an exam data file (it carries the correct answers) or an unexpected file got tracked"


def test_gate_every_data_file_and_the_clasp_link_are_git_ignored():
    paths = [f"parciales/apps-script/{publicar.data_file(target)}" for target in publicar.load_config()]
    paths.append("parciales/apps-script/.clasp.json")
    for path in paths:
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0, \
            f"{path} is not git-ignored; fix .gitignore"
