"""Precision, Recall, F1 evaluation against ground truth annotations."""

import json
import logging
from pathlib import Path
from dataclasses import dataclass

from ..detector.models import Finding, AnnotationStatus, RefactorResult

log = logging.getLogger("solid_analyzer")


@dataclass
class EvaluationMetrics:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    def compute(self):
        if self.true_positives + self.false_positives > 0:
            self.precision = self.true_positives / (self.true_positives + self.false_positives)
        if self.true_positives + self.false_negatives > 0:
            self.recall = self.true_positives / (self.true_positives + self.false_negatives)
        if self.precision + self.recall > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)

    def to_dict(self) -> dict:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
        }


def evaluate_detections(findings: list[Finding]) -> EvaluationMetrics:
    """Evaluate detection accuracy based on manual annotations.

    Findings annotated as CORRECT are true positives.
    Findings annotated as INCORRECT are false positives.
    False negatives come from ground truth (manually identified violations not detected).
    """
    metrics = EvaluationMetrics()

    for f in findings:
        if f.is_duplicate:
            continue
        if f.annotation == AnnotationStatus.CORRECT:
            metrics.true_positives += 1
        elif f.annotation == AnnotationStatus.INCORRECT:
            metrics.false_positives += 1
        # PENDING findings are not counted

    metrics.compute()
    return metrics


def evaluate_detections_with_ground_truth(
    findings: list[Finding],
    ground_truth_file: Path,
) -> EvaluationMetrics:
    """Evaluate detections against a ground truth file for false negative calculation."""
    metrics = evaluate_detections(findings)

    if ground_truth_file.exists():
        with open(ground_truth_file) as f:
            ground_truth = json.load(f)

        known_violations = ground_truth.get("violations", [])
        detected_keys = set()
        for f_item in findings:
            if not f_item.is_duplicate and f_item.annotation == AnnotationStatus.CORRECT:
                key = (f_item.principle, f_item.file_path, f_item.symbol_name)
                detected_keys.add(key)

        for violation in known_violations:
            key = (violation["principle"], violation["file_path"], violation["symbol_name"])
            if key not in detected_keys:
                metrics.false_negatives += 1

        metrics.compute()

    return metrics


def evaluate_refactorings(results: list[RefactorResult]) -> dict:
    """Evaluate refactoring success rates."""
    total = len(results)
    tests_passed = sum(1 for r in results if r.tests_passed)
    correct = sum(1 for r in results if r.annotation == AnnotationStatus.CORRECT)
    incorrect = sum(1 for r in results if r.annotation == AnnotationStatus.INCORRECT)

    return {
        "total_refactorings": total,
        "tests_passed": tests_passed,
        "tests_failed": total - tests_passed,
        "annotated_correct": correct,
        "annotated_incorrect": incorrect,
        "annotated_pending": total - correct - incorrect,
        "test_pass_rate": round(tests_passed / total, 4) if total > 0 else 0,
        "correctness_rate": round(correct / total, 4) if total > 0 else 0,
    }
