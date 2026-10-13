"""Tests of the multi-project publication (parciales/publicar.py) and its gates."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import formulario
import publicar

ROOT = Path(__file__).resolve().parent.parent.parent


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


def fake_apps_script(tmp_path):
    folder = tmp_path / "apps-script"
    folder.mkdir()
    (folder / "Code.gs").write_text("// code", encoding="utf-8")
    (folder / "appsscript.json").write_text("{}", encoding="utf-8")
    return folder


def test_the_config_maps_each_target_to_a_resolved_exam_and_skips_comments(tmp_path):
    path = write_config(tmp_path, {"_ayuda": "x", "practica": "real-1-practica", "parcial": "parcial-1-real"})
    assert publicar.load_config(path) == {"practica": "real-1-practica", "parcial": "parcial-1-real"}


@pytest.mark.parametrize("data, message", [
    ({"_ayuda": "solo comentarios"}, "no targets"),
    ({"Practica": "a"}, "lowercase"),
    ({"practica": ""}, "must name a resolved exam"),
    ({"practica": 3}, "must name a resolved exam"),
    ({"practica": "mismo", "parcial": "mismo"}, "more than one target"),
])
def test_a_config_that_would_publish_the_wrong_exam_is_rejected(tmp_path, data, message):
    with pytest.raises(publicar.PublishError, match=message):
        publicar.load_config(write_config(tmp_path, data))


def test_gate_the_real_config_is_valid_and_declares_both_projects():
    targets = publicar.load_config()
    assert {"practica", "parcial"} <= set(targets)    # a gate that finds nothing would pass green


def test_staging_copies_the_shared_source_and_generates_one_exam_data_per_target(tmp_path):
    apps = fake_apps_script(tmp_path)
    write_resolved(tmp_path / "specs", "uno", ["q001", "q002"])
    write_resolved(tmp_path / "specs", "dos", ["q001", "q003"])
    payloads = {t: publicar.build_payload(e, BANK, tmp_path / "specs", tmp_path / "banco.json")
                for t, e in {"practica": "uno", "parcial": "dos"}.items()}
    folders = {t: publicar.stage(t, p, apps) for t, p in payloads.items()}
    for folder in folders.values():
        for name in publicar.SOURCE_FILES:
            assert (folder / name).read_bytes() == (apps / name).read_bytes()
    data = {t: (f / "ExamData.gs").read_text(encoding="utf-8") for t, f in folders.items()}
    assert data["practica"] == formulario.render(payloads["practica"])
    assert data["practica"] != data["parcial"] and "enunciado 3" in data["parcial"] and "enunciado 3" not in data["practica"]


def test_swapping_the_exam_of_a_target_replaces_only_its_exam_data(tmp_path):
    apps = fake_apps_script(tmp_path)
    write_resolved(tmp_path / "specs", "uno", ["q001", "q002"])
    write_resolved(tmp_path / "specs", "dos", ["q001", "q003"])

    def build(exam):
        return publicar.build_payload(exam, BANK, tmp_path / "specs", tmp_path / "banco.json")

    publicar.stage("practica", build("uno"), apps)
    publicar.stage("parcial", build("dos"), apps)
    before = (apps / "parcial" / "ExamData.gs").read_text(encoding="utf-8")
    publicar.stage("practica", build("dos"), apps)
    assert "enunciado 3" in (apps / "practica" / "ExamData.gs").read_text(encoding="utf-8")
    assert (apps / "parcial" / "ExamData.gs").read_text(encoding="utf-8") == before


def test_a_missing_resolved_exam_says_which_command_creates_it(tmp_path):
    with pytest.raises(publicar.PublishError, match=r"armar\.py .*examen-que-no-existe\.local\.json"):
        publicar.build_payload("examen-que-no-existe", BANK, tmp_path, tmp_path / "banco.json")


def test_one_broken_target_leaves_every_target_untouched(tmp_path, monkeypatch, capsys):
    apps = fake_apps_script(tmp_path)
    specs = tmp_path / "specs"
    write_resolved(specs, "bueno", ["q001", "q002"])    # "roto" is never resolved
    (tmp_path / "banco.json").write_text(json.dumps(BANK), encoding="utf-8")
    config = write_config(tmp_path, {"practica": "bueno", "parcial": "roto"})
    monkeypatch.setattr(publicar, "APPS_SCRIPT_DIR", apps)
    monkeypatch.setattr(publicar, "SPECS_DIR", specs)
    assert publicar.main(["--config", str(config), "--bank", str(tmp_path / "banco.json")]) == 1
    assert "roto.resuelto.local.json not found" in capsys.readouterr().out
    assert not (apps / "practica").exists() and not (apps / "parcial").exists()


def test_only_stages_a_single_target_and_rejects_an_unknown_one(tmp_path, monkeypatch, capsys):
    apps = fake_apps_script(tmp_path)
    specs = tmp_path / "specs"
    write_resolved(specs, "bueno", ["q001", "q002"])
    write_resolved(specs, "otro", ["q001", "q003"])
    (tmp_path / "banco.json").write_text(json.dumps(BANK), encoding="utf-8")
    config = write_config(tmp_path, {"practica": "bueno", "parcial": "otro"})
    monkeypatch.setattr(publicar, "APPS_SCRIPT_DIR", apps)
    monkeypatch.setattr(publicar, "SPECS_DIR", specs)
    common = ["--config", str(config), "--bank", str(tmp_path / "banco.json")]
    assert publicar.main(common + ["--only", "parcial"]) == 0
    assert (apps / "parcial" / "ExamData.gs").exists() and not (apps / "practica").exists()
    assert publicar.main(common + ["--only", "nada"]) == 1
    assert "not in" in capsys.readouterr().out


def test_push_needs_clasp_and_a_linked_folder(tmp_path, monkeypatch):
    folder = tmp_path / "parcial"
    folder.mkdir()
    monkeypatch.setattr(publicar.shutil, "which", lambda name: None)
    with pytest.raises(publicar.PublishError, match="not on the PATH"):
        publicar.push(folder)
    monkeypatch.setattr(publicar.shutil, "which", lambda name: "clasp")
    with pytest.raises(publicar.PublishError, match="clasp create"):    # the message carries the one-time command
        publicar.push(folder)


def test_push_runs_clasp_from_the_target_folder_and_surfaces_a_failure(tmp_path, monkeypatch):
    folder = tmp_path / "parcial"
    folder.mkdir()
    (folder / ".clasp.json").write_text("{}", encoding="utf-8")
    calls = []

    def fake_run(command, cwd):
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0 if len(calls) == 1 else 1)

    monkeypatch.setattr(publicar.shutil, "which", lambda name: "clasp")
    monkeypatch.setattr(publicar.subprocess, "run", fake_run)
    publicar.push(folder)
    assert calls == [(["clasp", "push", "--force"], folder)]
    with pytest.raises(publicar.PublishError, match="previous ExamData.gs"):
        publicar.push(folder)


def test_gate_only_the_shared_source_of_apps_script_is_versioned():
    tracked = subprocess.run(["git", "ls-files", "parciales/apps-script"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split()
    assert sorted(tracked) == ["parciales/apps-script/Code.gs", "parciales/apps-script/appsscript.json"], \
        "a target folder (ExamData.gs carries the correct answers) or a copy of Code.gs got tracked"


def test_gate_every_target_of_the_config_is_git_ignored():
    """Discovered from publicacion.json, so a new target is covered the moment it is declared."""
    targets = publicar.load_config()
    for target in targets:
        for name in ("ExamData.gs", "Code.gs", "appsscript.json", ".clasp.json"):
            path = f"parciales/apps-script/{target}/{name}"
            assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0, \
                f"{path} is not git-ignored; fix .gitignore"
