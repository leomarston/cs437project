"""Data models for detection findings and issues."""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnnotationStatus(str, Enum):
    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"


@dataclass
class Finding:
    repo: str
    principle: str
    file_path: str
    symbol_name: str
    line_start: int
    line_end: int
    description: str
    reasoning: str
    severity: Severity = Severity.MEDIUM
    suggested_fix: str = ""
    scan_id: int = 0
    issue_id: str = ""
    is_duplicate: bool = False
    duplicate_of: str = ""
    annotation: AnnotationStatus = AnnotationStatus.PENDING
    annotation_reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.issue_id:
            self.issue_id = self.compute_issue_id()

    def compute_issue_id(self) -> str:
        key = f"{self.principle}|{self.file_path}|{self.symbol_name}|{self.line_start}-{self.line_end}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["annotation"] = self.annotation.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        data["severity"] = Severity(data.get("severity", "medium"))
        data["annotation"] = AnnotationStatus(data.get("annotation", "pending"))
        return cls(**data)


@dataclass
class RefactorResult:
    finding: Finding
    original_code: str
    refactored_code: str
    patch_diff: str
    files_changed: list[str]
    tests_passed: bool
    test_output: str
    metrics_before: dict = field(default_factory=dict)
    metrics_after: dict = field(default_factory=dict)
    annotation: AnnotationStatus = AnnotationStatus.PENDING
    annotation_reason: str = ""
    pr_report_path: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = {
            "finding": self.finding.to_dict(),
            "original_code": self.original_code,
            "refactored_code": self.refactored_code,
            "patch_diff": self.patch_diff,
            "files_changed": self.files_changed,
            "tests_passed": self.tests_passed,
            "test_output": self.test_output,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "annotation": self.annotation.value,
            "annotation_reason": self.annotation_reason,
            "pr_report_path": self.pr_report_path,
            "timestamp": self.timestamp,
        }
        return d


@dataclass
class ScanReport:
    repo: str
    principle: str
    scan_id: int
    prompt_variant: str
    temperature: float
    findings: list[Finding] = field(default_factory=list)
    new_findings: int = 0
    duplicate_findings: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "principle": self.principle,
            "scan_id": self.scan_id,
            "prompt_variant": self.prompt_variant,
            "temperature": self.temperature,
            "findings": [f.to_dict() for f in self.findings],
            "new_findings": self.new_findings,
            "duplicate_findings": self.duplicate_findings,
            "timestamp": self.timestamp,
        }
