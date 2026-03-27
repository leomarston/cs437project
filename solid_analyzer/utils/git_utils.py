"""Git utility functions for branch management and diffs."""

import subprocess
import logging
from pathlib import Path

log = logging.getLogger("solid_analyzer")


def run_git(repo_path: Path, *args: str) -> str:
    """Run a git command in the given repo and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        log.warning(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def create_branch(repo_path: Path, branch_name: str) -> str:
    return run_git(repo_path, "checkout", "-b", branch_name)


def checkout_branch(repo_path: Path, branch_name: str) -> str:
    return run_git(repo_path, "checkout", branch_name)


def get_current_branch(repo_path: Path) -> str:
    return run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")


def commit_changes(repo_path: Path, message: str) -> str:
    run_git(repo_path, "add", "-A")
    return run_git(repo_path, "commit", "-m", message)


def get_diff(repo_path: Path, staged: bool = False) -> str:
    if staged:
        return run_git(repo_path, "diff", "--cached")
    return run_git(repo_path, "diff")


def get_diff_stat(repo_path: Path) -> str:
    return run_git(repo_path, "diff", "--stat")


def stash_changes(repo_path: Path) -> str:
    return run_git(repo_path, "stash")


def stash_pop(repo_path: Path) -> str:
    return run_git(repo_path, "stash", "pop")


def reset_hard(repo_path: Path) -> str:
    return run_git(repo_path, "checkout", ".")
