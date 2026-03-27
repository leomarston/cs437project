"""Issue deduplication and registry management."""

import json
import logging
from pathlib import Path
from difflib import SequenceMatcher

from .models import Finding

log = logging.getLogger("solid_analyzer")


class IssueRegistry:
    """Tracks all detected findings and handles deduplication."""

    def __init__(self, registry_file: Path):
        self.registry_file = registry_file
        self._findings: dict[str, Finding] = {}
        self._load()

    def _load(self):
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                data = json.load(f)
            for item in data:
                finding = Finding.from_dict(item)
                self._findings[finding.issue_id] = finding

    def _save(self):
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        data = [f.to_dict() for f in self._findings.values()]
        with open(self.registry_file, "w") as f:
            json.dump(data, f, indent=2)

    def check_duplicate(self, new_finding: Finding) -> str | None:
        """Check if a finding is a duplicate of an existing one.

        Returns the issue_id of the duplicate if found, None otherwise.
        """
        for existing in self._findings.values():
            if existing.principle != new_finding.principle:
                continue
            if existing.file_path != new_finding.file_path:
                continue
            # Same symbol name
            if existing.symbol_name == new_finding.symbol_name:
                return existing.issue_id
            # Overlapping line ranges
            if (existing.line_start <= new_finding.line_end and
                    new_finding.line_start <= existing.line_end):
                # Check description similarity
                similarity = SequenceMatcher(
                    None,
                    existing.description.lower(),
                    new_finding.description.lower(),
                ).ratio()
                if similarity > 0.6:
                    return existing.issue_id

        return None

    def register(self, finding: Finding) -> bool:
        """Register a finding. Returns True if it's new, False if duplicate."""
        dup_id = self.check_duplicate(finding)
        if dup_id:
            finding.is_duplicate = True
            finding.duplicate_of = dup_id
            log.debug(f"Duplicate finding: {finding.issue_id} -> {dup_id}")
            self._save()
            return False

        self._findings[finding.issue_id] = finding
        self._save()
        return True

    def get_unique_findings(self, repo: str = None, principle: str = None) -> list[Finding]:
        """Get all unique (non-duplicate) findings, optionally filtered."""
        results = []
        for f in self._findings.values():
            if f.is_duplicate:
                continue
            if repo and f.repo != repo:
                continue
            if principle and f.principle != principle:
                continue
            results.append(f)
        return results

    def get_all_findings(self) -> list[Finding]:
        return list(self._findings.values())

    @property
    def unique_count(self) -> int:
        return sum(1 for f in self._findings.values() if not f.is_duplicate)

    @property
    def total_count(self) -> int:
        return len(self._findings)
