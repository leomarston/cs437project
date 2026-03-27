"""Python language handler."""

from pathlib import Path
from .base import LanguageHandler


class PythonHandler(LanguageHandler):
    def get_file_extensions(self) -> list[str]:
        return [".py"]

    def get_test_command(self, repo_path: Path) -> str:
        if (repo_path / "pytest.ini").exists() or (repo_path / "pyproject.toml").exists():
            return "pytest tests/ -v"
        return "python -m pytest tests/ -v"

    def get_build_command(self, repo_path: Path) -> str | None:
        return None

    def get_language_name(self) -> str:
        return "python"
