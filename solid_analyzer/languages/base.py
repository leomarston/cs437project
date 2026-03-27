"""Base language handler interface."""

from abc import ABC, abstractmethod
from pathlib import Path


class LanguageHandler(ABC):
    """Abstract base class for language-specific operations."""

    @abstractmethod
    def get_file_extensions(self) -> list[str]:
        pass

    @abstractmethod
    def get_test_command(self, repo_path: Path) -> str:
        pass

    @abstractmethod
    def get_build_command(self, repo_path: Path) -> str | None:
        pass

    @abstractmethod
    def get_language_name(self) -> str:
        pass
