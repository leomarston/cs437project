"""File discovery and filtering for source code analysis."""

import logging
from pathlib import Path

log = logging.getLogger("solid_analyzer")

LANGUAGE_EXTENSIONS = {
    "java": [".java"],
    "kotlin": [".kt", ".kts"],
    "python": [".py"],
}

SKIP_DIRS = {
    ".git", "node_modules", "build", "target", ".gradle", ".idea",
    "__pycache__", ".pytest_cache", "dist", ".eggs", "vendor",
    "test", "tests", "src/test", "testFixtures",
}


class FileSelector:
    """Selects source files from a repository for analysis."""

    def __init__(self, language: str, source_dirs: list[str] | None = None):
        self.language = language
        self.extensions = LANGUAGE_EXTENSIONS.get(language, [])
        self.source_dirs = source_dirs

    def select_files(self, repo_path: Path) -> list[Path]:
        """Find all analyzable source files in the repository."""
        files = []

        if self.source_dirs:
            search_dirs = [repo_path / d for d in self.source_dirs]
        else:
            search_dirs = [repo_path]

        for search_dir in search_dirs:
            if not search_dir.exists():
                log.warning(f"Source directory not found: {search_dir}")
                continue
            for ext in self.extensions:
                for file_path in search_dir.rglob(f"*{ext}"):
                    if self._should_include(file_path, repo_path):
                        files.append(file_path)

        log.info(f"Found {len(files)} {self.language} source files in {repo_path.name}")
        return sorted(files)

    def _should_include(self, file_path: Path, repo_path: Path) -> bool:
        """Check if a file should be included in analysis."""
        rel_parts = file_path.relative_to(repo_path).parts
        # Skip test directories
        for part in rel_parts:
            if part.lower() in SKIP_DIRS:
                return False
        # Skip test files by naming convention
        name = file_path.stem.lower()
        if name.startswith("test_") or name.endswith("_test") or name.endswith("test"):
            return False
        # Skip very small files (< 10 lines)
        try:
            line_count = sum(1 for _ in open(file_path, errors="ignore"))
            if line_count < 10:
                return False
        except (OSError, UnicodeDecodeError):
            return False
        return True
