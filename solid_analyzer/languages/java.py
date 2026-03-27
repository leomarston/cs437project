"""Java language handler."""

from pathlib import Path
from .base import LanguageHandler


class JavaHandler(LanguageHandler):
    def get_file_extensions(self) -> list[str]:
        return [".java"]

    def get_test_command(self, repo_path: Path) -> str:
        if (repo_path / "gradlew").exists():
            return "./gradlew test"
        if (repo_path / "pom.xml").exists():
            return "mvn test -Dmaven.test.failure.ignore=true"
        return "mvn test"

    def get_build_command(self, repo_path: Path) -> str | None:
        if (repo_path / "gradlew").exists():
            return "./gradlew build -x test"
        if (repo_path / "pom.xml").exists():
            return "mvn compile -q"
        return None

    def get_language_name(self) -> str:
        return "java"
