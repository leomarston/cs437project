"""Generate PR-style reports for each refactoring."""

import logging
from pathlib import Path
from datetime import datetime

from ..detector.models import Finding, RefactorResult

log = logging.getLogger("solid_analyzer")


def generate_pr_report(result: RefactorResult, output_dir: Path) -> Path:
    """Generate a markdown PR-style report for a refactoring attempt."""
    finding = result.finding
    report_name = f"PR_{finding.issue_id}_{finding.principle}.md"
    report_path = output_dir / report_name

    output_dir.mkdir(parents=True, exist_ok=True)

    test_status = "PASSED ✅" if result.tests_passed else "FAILED ❌"
    annotation = result.annotation.value.upper()

    # Metrics comparison
    metrics_section = ""
    if result.metrics_before and result.metrics_after:
        metrics_section = _format_metrics_comparison(result.metrics_before, result.metrics_after)

    report = f"""# Refactoring PR: {finding.principle} Violation Fix

**Issue ID:** `{finding.issue_id}`
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Repository:** {finding.repo}
**Principle:** {finding.principle}
**Annotation Status:** {annotation}

---

## Violation Details

- **File:** `{finding.file_path}`
- **Symbol:** `{finding.symbol_name}`
- **Lines:** {finding.line_start}-{finding.line_end}
- **Severity:** {finding.severity.value}

### Description
{finding.description}

### Reasoning
{finding.reasoning}

---

## Changes Made

### Files Changed
{chr(10).join(f'- `{f}`' for f in result.files_changed)}

### Diff
```diff
{result.patch_diff}
```

---

## Test Results

**Status:** {test_status}

```
{result.test_output[:2000]}
```

{metrics_section}

---

## Manual Review

**Annotation:** {annotation}
**Reason:** {result.annotation_reason or 'Pending review'}
"""

    report_path.write_text(report, encoding="utf-8")
    log.info(f"Generated PR report: {report_path}")
    return report_path


def _format_metrics_comparison(before: dict, after: dict) -> str:
    """Format a before/after metrics comparison table."""
    lines = [
        "## Code Quality Metrics",
        "",
        "| Metric | Before | After | Change |",
        "|--------|--------|-------|--------|",
    ]

    all_keys = set(list(before.keys()) + list(after.keys()))
    for key in sorted(all_keys):
        b_val = before.get(key, "N/A")
        a_val = after.get(key, "N/A")
        if isinstance(b_val, (int, float)) and isinstance(a_val, (int, float)):
            change = a_val - b_val
            direction = "📈" if change > 0 else "📉" if change < 0 else "—"
            lines.append(f"| {key} | {b_val} | {a_val} | {change:+.2f} {direction} |")
        else:
            lines.append(f"| {key} | {b_val} | {a_val} | — |")

    return "\n".join(lines)
