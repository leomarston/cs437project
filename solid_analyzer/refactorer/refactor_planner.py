"""Plans and generates refactoring patches using the Gemini API."""

import logging
from pathlib import Path
from typing import Optional

from ..detector.gemini_client import GeminiClient
from ..detector.models import Finding
from ..detector.prompts import build_refactoring_prompt
from ..detector.response_parser import parse_refactoring_response
from ..scanner.chunker import read_file_content

log = logging.getLogger("solid_analyzer")


class RefactorPlanner:
    """Uses Gemini to generate refactoring plans for detected violations."""

    def __init__(self, gemini_client: GeminiClient, repo_path: Path, language: str):
        self.client = gemini_client
        self.repo_path = repo_path
        self.language = language

    def plan_refactoring(self, finding: Finding) -> Optional[dict]:
        """Generate a refactoring plan for a given finding.

        Returns dict with 'explanation' and 'refactored_files' or None on failure.
        """
        file_path = Path(finding.file_path)
        if not file_path.is_absolute():
            file_path = self.repo_path / file_path

        original_code = read_file_content(file_path)
        if not original_code:
            log.error(f"Could not read file: {file_path}")
            return None

        prompt = build_refactoring_prompt(
            principle=finding.principle,
            original_code=original_code,
            file_path=finding.file_path,
            language=self.language,
            symbol_name=finding.symbol_name,
            line_start=finding.line_start,
            line_end=finding.line_end,
            description=finding.description,
            reasoning=finding.reasoning,
        )

        try:
            response = self.client.generate(prompt, expect_json=True)
            result = parse_refactoring_response(response)
            if result:
                log.info(f"Generated refactoring plan for {finding.symbol_name} in {finding.file_path}")
            return result
        except Exception as e:
            log.error(f"Failed to generate refactoring plan: {e}")
            return None
