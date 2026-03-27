"""Generate aggregate summary reports across all repos and principles."""

import json
import logging
from pathlib import Path
from datetime import datetime

from ..detector.models import Finding, RefactorResult
from ..metrics.evaluation import evaluate_detections, evaluate_refactorings, EvaluationMetrics

log = logging.getLogger("solid_analyzer")

PRINCIPLES = ["SRP", "OCP", "LSP", "ISP", "DIP"]


def generate_summary_report(
    findings: list[Finding],
    refactor_results: list[RefactorResult],
    budget_summary: dict,
    output_dir: Path,
    repo_name: str = "all",
) -> Path:
    """Generate a comprehensive summary report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"summary_{repo_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    # Detection stats
    unique_findings = [f for f in findings if not f.is_duplicate]
    detection_eval = evaluate_detections(unique_findings)
    refactor_eval = evaluate_refactorings(refactor_results) if refactor_results else {}

    # Per-principle breakdown
    principle_stats = {}
    for p in PRINCIPLES:
        p_findings = [f for f in unique_findings if f.principle == p]
        p_refactors = [r for r in refactor_results if r.finding.principle == p]
        principle_stats[p] = {
            "findings": len(p_findings),
            "refactorings": len(p_refactors),
            "tests_passed": sum(1 for r in p_refactors if r.tests_passed),
        }

    report = f"""# SOLID Analyzer - Summary Report

**Repository:** {repo_name}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Student:** Ahmet Yağız Sarıdoğan

---

## Budget Usage

| Metric | Count |
|--------|-------|
| Total Detections | {budget_summary.get('total_detections', 0)} / 60 |
| Total Refactorings | {budget_summary.get('total_refactorings', 0)} / 60 |

### Per-Principle Budget

| Principle | Detections | Refactorings |
|-----------|-----------|--------------|
"""

    for p in PRINCIPLES:
        det = budget_summary.get("detections", {}).get(p, 0)
        ref = budget_summary.get("refactorings", {}).get(p, 0)
        report += f"| {p} | {det} / 12 | {ref} / 12 |\n"

    report += f"""
---

## Detection Results

| Metric | Value |
|--------|-------|
| Total Findings | {len(findings)} |
| Unique Findings | {len(unique_findings)} |
| Duplicate Findings | {len(findings) - len(unique_findings)} |

### Detection Accuracy (Based on Annotations)

| Metric | Value |
|--------|-------|
| True Positives | {detection_eval.true_positives} |
| False Positives | {detection_eval.false_positives} |
| False Negatives | {detection_eval.false_negatives} |
| **Precision** | **{detection_eval.precision:.4f}** |
| **Recall** | **{detection_eval.recall:.4f}** |
| **F1 Score** | **{detection_eval.f1_score:.4f}** |

### Findings by Principle

| Principle | Unique Findings | Refactorings | Tests Passed |
|-----------|----------------|-------------|--------------|
"""

    for p in PRINCIPLES:
        stats = principle_stats[p]
        report += f"| {p} | {stats['findings']} | {stats['refactorings']} | {stats['tests_passed']} |\n"

    if refactor_eval:
        report += f"""
---

## Refactoring Results

| Metric | Value |
|--------|-------|
| Total Refactorings | {refactor_eval.get('total_refactorings', 0)} |
| Tests Passed | {refactor_eval.get('tests_passed', 0)} |
| Tests Failed | {refactor_eval.get('tests_failed', 0)} |
| Test Pass Rate | {refactor_eval.get('test_pass_rate', 0):.2%} |
| Annotated Correct | {refactor_eval.get('annotated_correct', 0)} |
| Annotated Incorrect | {refactor_eval.get('annotated_incorrect', 0)} |
| Correctness Rate | {refactor_eval.get('correctness_rate', 0):.2%} |
"""

    report_path.write_text(report, encoding="utf-8")
    log.info(f"Generated summary report: {report_path}")
    return report_path


def export_findings_csv(findings: list[Finding], output_path: Path):
    """Export findings to CSV for analysis."""
    import csv

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "issue_id", "repo", "principle", "file_path", "symbol_name",
            "line_start", "line_end", "severity", "description",
            "is_duplicate", "annotation", "scan_id",
        ])
        for finding in findings:
            writer.writerow([
                finding.issue_id, finding.repo, finding.principle,
                finding.file_path, finding.symbol_name,
                finding.line_start, finding.line_end,
                finding.severity.value, finding.description,
                finding.is_duplicate, finding.annotation.value,
                finding.scan_id,
            ])
    log.info(f"Exported {len(findings)} findings to {output_path}")
