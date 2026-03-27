"""Repository cloning and management."""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("solid_analyzer")


class RepoManager:
    """Manages cloning and setup of target repositories."""

    def __init__(self, repos_dir: Path):
        self.repos_dir = repos_dir
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    def clone_or_update(self, url: str, name: str, branch: str = "main") -> Path:
        """Clone a repository or pull latest changes if it already exists."""
        repo_path = self.repos_dir / name

        if repo_path.exists() and (repo_path / ".git").exists():
            log.info(f"Repository '{name}' already exists, pulling latest changes...")
            subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return repo_path

        log.info(f"Cloning '{url}' into '{repo_path}'...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone {url}: {result.stderr}")

        log.info(f"Successfully cloned '{name}'")
        return repo_path

    def get_repo_path(self, name: str) -> Path:
        repo_path = self.repos_dir / name
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository '{name}' not found at {repo_path}")
        return repo_path
