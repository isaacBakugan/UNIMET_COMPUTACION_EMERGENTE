"""Keep the local clones of the team repos in sync with GitHub, without touching their working tree.

Only `git fetch` (plus a first `git clone` when missing): graders then read `origin/HEAD`, so there
is no `reset --hard` and nothing local can be lost or drift from the remote.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def sync_clone(url: str, repo: Path) -> str:
    """Clone `url` into `repo` if missing, else fetch. Returns a one-line status for the log."""
    if not (repo / ".git").exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        result = run_git("clone", url, str(repo))
        action = "cloned"
    else:
        run_git("-C", str(repo), "remote", "set-url", "origin", url)
        result = run_git("-C", str(repo), "fetch", "--prune", "origin")
        action = "fetched"
    if result.returncode != 0:
        raise RuntimeError(f"git {action} failed for {url}: {result.stderr.strip()}")
    # A clone may predate the origin/HEAD pointer; make sure it exists so graders can use it.
    run_git("-C", str(repo), "remote", "set-head", "origin", "--auto")
    return action
