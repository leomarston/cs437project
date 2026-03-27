"""Violation seeder: injects SOLID violations into repositories when they are too clean."""

import json
import logging
from pathlib import Path
from datetime import datetime

from .detector.gemini_client import GeminiClient
from .detector.response_parser import _parse_json_safely
from .scanner.file_selector import FileSelector
from .scanner.chunker import read_file_content

log = logging.getLogger("solid_analyzer")

SEED_PROMPT = """
You are a software engineering instructor creating examples of SOLID principle violations
for educational purposes.

Given the following {language} source file, inject a realistic {principle} violation into the code.
The violation should:
1. Be realistic and representative of common violations found in production code
2. Not break the compilation/syntax of the file
3. Be clearly identifiable as a {principle} violation
4. Be moderate in severity

## Original Code
**File:** `{file_path}`
```{language}
{code}
```

## Instructions
Modify the code to introduce a {principle} violation. Return JSON with:
```json
{{
  "modified_code": "Full modified file content with the injected violation",
  "description": "Description of the injected violation",
  "violation_location": {{
    "symbol_name": "Name of the class/method/function where violation was injected",
    "line_start": 1,
    "line_end": 50
  }},
  "explanation": "Why this constitutes a {principle} violation"
}}
```
"""


class ViolationSeeder:
    """Injects SOLID violations into source files for testing detection capabilities."""

    def __init__(self, gemini_client: GeminiClient, repo_path: Path, language: str):
        self.client = gemini_client
        self.repo_path = repo_path
        self.language = language

    def seed_violations(self, principle: str, count: int = 5) -> list[dict]:
        """Inject violations for a given principle into randomly selected files."""
        selector = FileSelector(self.language)
        files = selector.select_files(self.repo_path)

        if not files:
            log.error(f"No source files found in {self.repo_path}")
            return []

        # Pick files spread across the codebase
        step = max(1, len(files) // count)
        selected = files[::step][:count]

        results = []
        for file_path in selected:
            result = self._seed_single_violation(file_path, principle)
            if result:
                results.append(result)

        return results

    def _seed_single_violation(self, file_path: Path, principle: str) -> dict | None:
        """Inject a violation into a single file."""
        original_code = read_file_content(file_path)
        if not original_code or len(original_code) < 50:
            return None

        rel_path = str(file_path.relative_to(self.repo_path))

        prompt = SEED_PROMPT.format(
            language=self.language,
            principle=principle,
            file_path=rel_path,
            code=original_code[:5000],  # Limit code size
        )

        try:
            response = self.client.generate(prompt, expect_json=True)
            data = _parse_json_safely(response)

            if not data or not isinstance(data, dict):
                return None

            modified_code = data.get("modified_code", "")
            if not modified_code:
                return None

            # Save original as backup
            backup_path = file_path.with_suffix(file_path.suffix + ".original")
            if not backup_path.exists():
                backup_path.write_text(original_code, encoding="utf-8")

            # Write modified code
            file_path.write_text(modified_code, encoding="utf-8")

            result = {
                "file_path": rel_path,
                "principle": principle,
                "description": data.get("description", ""),
                "explanation": data.get("explanation", ""),
                "violation_location": data.get("violation_location", {}),
                "backup_file": str(backup_path.relative_to(self.repo_path)),
                "is_seeded": True,
                "timestamp": datetime.now().isoformat(),
            }

            log.info(f"Seeded {principle} violation in {rel_path}")
            return result

        except Exception as e:
            log.error(f"Failed to seed violation in {rel_path}: {e}")
            return None
