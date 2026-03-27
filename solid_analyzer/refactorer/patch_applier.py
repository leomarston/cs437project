"""Applies refactoring patches to source files."""

import logging
import shutil
from pathlib import Path

from ..utils.git_utils import run_git, create_branch, get_current_branch

log = logging.getLogger("solid_analyzer")


class PatchApplier:
    """Applies refactoring changes to source files with git branch management."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._original_branch = get_current_branch(repo_path)

    def apply_refactoring(self, refactoring_plan: dict, issue_id: str) -> list[str]:
        """Apply a refactoring plan to the repository.

        Creates a new branch, applies file changes, and returns list of changed files.
        """
        branch_name = f"refactor/{issue_id}"
        files_changed = []

        try:
            # Create a dedicated branch
            create_branch(self.repo_path, branch_name)
        except Exception:
            # Branch may already exist; try checking it out
            try:
                run_git(self.repo_path, "checkout", branch_name)
            except Exception as e:
                log.error(f"Could not create/checkout branch {branch_name}: {e}")
                return []

        refactored_files = refactoring_plan.get("refactored_files", [])
        for file_info in refactored_files:
            file_path_str = file_info.get("file_path", "")
            action = file_info.get("action", "modify")
            content = file_info.get("content", "")

            if not file_path_str or not content:
                continue

            target_path = self.repo_path / file_path_str
            try:
                if action == "create":
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                elif action == "modify" and not target_path.exists():
                    log.warning(f"File to modify not found: {target_path}")
                    continue

                target_path.write_text(content, encoding="utf-8")
                files_changed.append(file_path_str)
                log.info(f"Applied {action} to {file_path_str}")
            except OSError as e:
                log.error(f"Failed to write {file_path_str}: {e}")

        return files_changed

    def rollback(self):
        """Roll back all changes and return to the original branch."""
        run_git(self.repo_path, "checkout", ".")
        if self._original_branch:
            run_git(self.repo_path, "checkout", self._original_branch)

    def commit_refactoring(self, issue_id: str, principle: str, description: str) -> str:
        """Commit the refactoring changes."""
        message = f"refactor({principle}): {description}\n\nIssue: {issue_id}"
        run_git(self.repo_path, "add", "-A")
        return run_git(self.repo_path, "commit", "-m", message)

    def get_diff(self) -> str:
        """Get the current diff of changes."""
        return run_git(self.repo_path, "diff")

    def return_to_main(self):
        """Return to the original branch."""
        if self._original_branch:
            run_git(self.repo_path, "checkout", self._original_branch)
