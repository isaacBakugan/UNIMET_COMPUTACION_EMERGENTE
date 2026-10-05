"""Run student programs in a bubblewrap sandbox (no network, read-only sources) and read the evidence.

On Windows the sandbox lives in WSL Ubuntu (`wsl.exe -d Ubuntu -- bwrap ...`); on Linux it
calls bwrap directly. Needed once: `apt install bubblewrap python3-matplotlib` in Ubuntu.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rubrica import CaseEvidence, color_category

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "sandbox_runner.py"
CASES_DIR = HERE / "tarea-1" / "casos"
WSL_PREFIX = ["wsl.exe", "-d", "Ubuntu", "--"] if sys.platform == "win32" else []

# case -> (csv path inside the sandbox, answer to the dataset menu of the student program)
CASE_INPUTS = {
    "given_separable": ("/src/assets/fuzzy_separables.csv", "2"),
    "given_non_separable": ("/src/assets/no_separables.csv", "1"),
    "hidden_separable": ("/data/oculto_separable.csv", "3"),
    "hidden_non_separable": ("/data/oculto_no_separable.csv", "3"),
}


def to_sandbox_path(path: Path) -> str:
    """Windows `C:\\x\\y` -> `/mnt/c/x/y` (WSL); identity on Linux."""
    resolved = path.resolve()
    if sys.platform != "win32":
        return str(resolved)
    if not resolved.drive:
        raise ValueError(f"Expected an absolute Windows path: {resolved}")
    return "/mnt/" + resolved.drive[0].lower() + str(resolved)[2:].replace("\\", "/")


def check_runtime() -> None:
    """Fail early with an actionable message if the sandbox is not usable."""
    probes = [
        (["bwrap", "--version"], "bubblewrap"),
        (["/usr/bin/python3", "-c", "import matplotlib"], "python3-matplotlib"),
    ]
    for command, package in probes:
        try:
            subprocess.run([*WSL_PREFIX, *command], check=True, capture_output=True, timeout=60)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(
                f"Sandbox not ready ({package}). In Ubuntu run: sudo apt install bubblewrap python3-matplotlib"
            ) from exc


def _bwrap_command(source_dir: Path, filename: str, out_dir: Path, csv_path: str, case: str, menu_choice: str) -> list[str]:
    return [
        *WSL_PREFIX, "bwrap", "--unshare-all", "--die-with-parent",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64", "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/etc", "/etc", "--dev", "/dev", "--proc", "/proc",
        "--tmpfs", "/tmp", "--ro-bind", to_sandbox_path(source_dir), "/src",
        "--ro-bind", to_sandbox_path(CASES_DIR), "/data",
        "--dir", "/runner", "--ro-bind", to_sandbox_path(RUNNER), "/runner/sandbox_runner.py",
        "--bind", to_sandbox_path(out_dir), "/out",
        "--setenv", "HOME", "/tmp", "--setenv", "MPLCONFIGDIR", "/tmp/mpl",
        "--setenv", "MPLBACKEND", "Agg", "--setenv", "PYTHONNOUSERSITE", "1",
        "--chdir", "/src", "/usr/bin/python3", "/runner/sandbox_runner.py",
        "/src/" + filename, csv_path, case, menu_choice,
    ]


def run_case(source_dir: Path, filename: str, case: str, out_dir: Path, timeout: int = 40) -> CaseEvidence:
    """Run one student file against one case; `source_dir` is the exported tarea-1-codigo/."""
    csv_path, menu_choice = CASE_INPUTS[case]
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in (*out_dir.glob("grafico_*.png"), out_dir / "traza.json"):
        stale.unlink(missing_ok=True)
    command = _bwrap_command(source_dir, filename, out_dir, csv_path, case, menu_choice)
    try:
        run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=timeout)
        status = "ok" if run.returncode == 0 else f"error_{run.returncode}"
        stdout, stderr = run.stdout, run.stderr
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    (out_dir / "salida.txt").write_text(stdout, encoding="utf-8")
    (out_dir / "errores.txt").write_text(stderr, encoding="utf-8")
    return read_evidence(out_dir, status)


def read_evidence(out_dir: Path, status: str) -> CaseEvidence:
    """Condense traza.json into the counts the rubric needs (3rd axis of the richest figure)."""
    evidence = CaseEvidence(status=status)
    trace_file = out_dir / "traza.json"
    if not trace_file.exists():
        return evidence
    try:
        trace = json.loads(trace_file.read_text(encoding="utf-8"))
    except ValueError:
        return evidence
    figures = trace.get("figures", [])
    evidence.plots = len(figures)
    error = trace.get("error", "").strip().splitlines()
    evidence.failure = error[-1] if error else ""
    candidates = [figure for figure in figures if len(figure["axes_detail"]) >= 3]
    if not candidates:
        return evidence
    main = max(candidates, key=lambda figure: len(figure["axes_detail"]))
    expected, predicted, compared = main["axes_detail"][:3]
    evidence.expected_points = expected["points"]
    evidence.predicted_points = predicted["points"]
    evidence.compared_points = compared["points"]
    for color, count in compared["colors"].items():
        category = color_category(color)
        if category == "green":
            evidence.green += count
        elif category == "red":
            evidence.red += count
    evidence.figure = main["file"]
    return evidence
