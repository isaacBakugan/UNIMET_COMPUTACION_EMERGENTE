"""Read student submissions out of the local clones, read-only.

The clones in `.repos-trimestre-<term>/` are refreshed by `tareas/verify_submissions.py`.
Here we never touch their working tree: the commit evaluated is resolved with
`git rev-list --before=<cutoff>` and its `tarea-1-codigo/` is exported with `git archive`.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ASSIGNMENT_DIR = "tarea-1-codigo"
PERCEPTRON_FILES = ("perceptron_1.py", "perceptron_2.py", "perceptron_3.py")
ALLOWED_IMPORTS = {"matplotlib"}


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo.name}: {result.stderr.strip()}")
    return result.stdout.strip()


def to_utc_iso(value: str) -> str:
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError(f"The cutoff must include a timezone, e.g. -04:00: {value}")
    return date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def commit_at_cutoff(repo: Path, cutoff: str, ref: str = "HEAD") -> str | None:
    """Last commit reachable from `ref` whose commit date is <= cutoff, or None."""
    sha = git(repo, "rev-list", "-1", f"--before={to_utc_iso(cutoff)}", ref)
    return sha or None


def commits_after_cutoff(repo: Path, cutoff: str, ref: str = "HEAD", folder: str | None = None) -> list[str]:
    """ISO dates of the commits after the cutoff (optionally only those touching `folder`), newest first."""
    args = ["log", f"--after={to_utc_iso(cutoff)}", "--format=%cI", ref]
    if folder:
        args += ["--", folder]
    return git(repo, *args).splitlines()


def remote_ref(repo: Path) -> str:
    """The remote default branch (origin/HEAD) when the clone has one; HEAD otherwise."""
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "origin/HEAD"],
                            capture_output=True, text=True)
    return "origin/HEAD" if result.returncode == 0 else "HEAD"


def commit_exists(repo: Path, sha: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True).returncode == 0


def commit_date(repo: Path, sha: str) -> str:
    return git(repo, "show", "-s", "--format=%cI", sha)


def export_assignment(repo: Path, sha: str, destination: Path, folder: str = ASSIGNMENT_DIR) -> Path:
    """Extract `folder` (default `tarea-1-codigo/`) at `sha` into `destination`; return the extracted folder.

    Returns a possibly empty folder when the folder does not exist at that commit.
    """
    destination.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", sha, folder],
                            capture_output=True, timeout=120)
    if result.returncode == 0:
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
            archive.extractall(destination, filter="data")
    return destination / folder


def student_identity(source: str) -> tuple[str, str]:
    """Name and ID read from the header comments of the file ('' when absent)."""
    name = identity_number = ""
    for line in source.splitlines()[:25]:
        match = re.match(r"\s*#\s*nombre(?: del integrante)?\s*:\s*(.+)", line, re.I)
        if match and match.group(1).strip():
            name = match.group(1).strip()
        match = re.match(r"\s*#\s*c[eé]dula(?: del integrante)?\s*:\s*(.+)", line, re.I)
        if match and match.group(1).strip():
            identity_number = match.group(1).strip()
        if not name:
            match = re.match(r"\s*#\s*tarea\s*1\s+(.+)", line, re.I)
            if match and match.group(1).strip():
                name = match.group(1).strip()
    return name, identity_number


def static_review(source: str) -> dict:
    """Syntax / empty-template / forbidden-imports check. Never executes the code."""
    review = {"syntax_ok": True, "empty": False, "forbidden_imports": []}
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        review["syntax_ok"] = False
        review["syntax_error"] = f"line {exc.lineno}: {exc.msg}"
        return review
    review["empty"] = not tree.body
    forbidden = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            forbidden.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            forbidden.add((node.module or "relative import").split(".")[0])
    review["forbidden_imports"] = sorted(forbidden - ALLOWED_IMPORTS)
    return review
