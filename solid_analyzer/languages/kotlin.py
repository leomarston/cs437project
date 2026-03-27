"""Kotlin language handler."""

from pathlib import Path
from .base import LanguageHandler


class KotlinHandler(LanguageHandler):
    def get_file_extensions(self) -> list[str]:
        return [".kt", ".kts"]

    def get_test_command(self, repo_path: Path) -> str:
        if (repo_path / "gradlew").exists():
            return "./gradlew test"
        return "gradle test"

    def get_build_command(self, repo_path: Path) -> str | None:
        if (repo_path / "gradlew").exists():
            return "./gradlew build -x test"
        return "gradle build -x test"

    def get_language_name(self) -> str:
        return "kotlin"
