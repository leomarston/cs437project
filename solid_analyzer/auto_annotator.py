"""Auto-annotation: uses a second LLM pass to verify findings and refactorings."""

import json
import logging
from pathlib import Path

from .detector.gemini_client import GeminiClient
from .detector.models import Finding, AnnotationStatus
from .detector.response_parser import _parse_json_safely
from .scanner.chunker import read_file_content

log = logging.getLogger("solid_analyzer")

VERIFY_DETECTION_PROMPT = """
You are a senior software architect performing a code review. You need to verify whether
a reported SOLID principle violation is a TRUE violation or a FALSE POSITIVE.

## Reported Violation
- **Principle:** {principle}
- **File:** `{file_path}`
- **Symbol:** `{symbol_name}`
- **Lines:** {line_start}-{line_end}
- **Description:** {description}
- **Reasoning:** {reasoning}

## Source Code
```{language}
{code}
```

## Instructions
Carefully analyze the code and the reported violation. Determine if this is:
1. A **correct** violation — the code genuinely violates the stated SOLID principle
2. An **incorrect** report — the code does NOT violate the principle, or the reasoning is flawed

Be strict but fair. Minor style issues are NOT violations. The violation must be a clear
design issue that would benefit from refactoring.

Return JSON:
```json
{{
  "is_correct": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Brief explanation of why this is or isn't a valid violation"
}}
```
"""

VERIFY_REFACTORING_PROMPT = """
You are a senior software architect reviewing a code refactoring. Determine whether the
refactoring correctly addresses the reported SOLID violation without introducing regressions.

## Violation Being Fixed
- **Principle:** {principle}
- **Description:** {description}

## Files Changed
{files_changed}

## Diff
```diff
{diff}
```

## Test Results
Tests passed: {tests_passed}

## Instructions
Evaluate whether this refactoring:
1. Correctly addresses the stated SOLID principle violation
2. Doesn't introduce new design issues
3. Maintains backward compatibility
4. Is a meaningful improvement (not just cosmetic)

Return JSON:
```json
{{
  "is_correct": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Brief explanation of the assessment"
}}
```
"""


class AutoAnnotator:
    """Uses a second LLM pass to automatically verify and annotate findings."""

    def __init__(self, gemini_client: GeminiClient, repo_path: Path, language: str):
        self.client = gemini_client
        self.repo_path = repo_path
        self.language = language

    def annotate_finding(self, finding: Finding) -> tuple[AnnotationStatus, str]:
        """Verify a single detection finding using Gemini."""
        file_path = self.repo_path / finding.file_path
        code = ""
        if file_path.exists():
            code = read_file_content(file_path)
            # Extract relevant section with context
            lines = code.splitlines()
            start = max(0, finding.line_start - 10)
            end = min(len(lines), finding.line_end + 10)
            code = "\n".join(lines[start:end])

        if not code:
            code = "(File not found or empty)"

        prompt = VERIFY_DETECTION_PROMPT.format(
            principle=finding.principle,
            file_path=finding.file_path,
            symbol_name=finding.symbol_name,
            line_start=finding.line_start,
            line_end=finding.line_end,
            description=finding.description,
            reasoning=finding.reasoning,
            language=self.language,
            code=code[:8000],
        )

        try:
            response = self.client.generate(prompt, temperature=0.1, expect_json=True)
            data = _parse_json_safely(response)
            if data and isinstance(data, dict):
                is_correct = data.get("is_correct", True)
                reason = data.get("reason", "Auto-verified by LLM")
                confidence = data.get("confidence", 0.5)

                status = AnnotationStatus.CORRECT if is_correct else AnnotationStatus.INCORRECT
                annotation_reason = f"[Auto, confidence={confidence:.2f}] {reason}"
                return status, annotation_reason
        except Exception as e:
            log.warning(f"Auto-annotation failed for {finding.issue_id}: {e}")

        return AnnotationStatus.PENDING, ""

    def annotate_refactoring(self, result_data: dict) -> tuple[str, str]:
        """Verify a single refactoring result using Gemini."""
        finding = result_data.get("finding", {})
        diff = result_data.get("patch_diff", "")[:5000]
        tests_passed = result_data.get("tests_passed", False)
        files_changed = ", ".join(result_data.get("files_changed", []))

        prompt = VERIFY_REFACTORING_PROMPT.format(
            principle=finding.get("principle", ""),
            description=finding.get("description", ""),
            files_changed=files_changed,
            diff=diff,
            tests_passed=tests_passed,
        )

        try:
            response = self.client.generate(prompt, temperature=0.1, expect_json=True)
            data = _parse_json_safely(response)
            if data and isinstance(data, dict):
                is_correct = data.get("is_correct", True)
                reason = data.get("reason", "Auto-verified by LLM")
                confidence = data.get("confidence", 0.5)

                status = "correct" if is_correct else "incorrect"
                annotation_reason = f"[Auto, confidence={confidence:.2f}] {reason}"
                return status, annotation_reason
        except Exception as e:
            log.warning(f"Auto-annotation failed for refactoring: {e}")

        return "pending", ""


def auto_annotate_detections(
    gemini_client: GeminiClient,
    registry_file: Path,
    repo_path: Path,
    language: str,
) -> int:
    """Auto-annotate all pending detection findings for a repo."""
    if not registry_file.exists():
        log.error(f"Registry file not found: {registry_file}")
        return 0

    with open(registry_file) as f:
        findings_data = json.load(f)

    findings = [Finding.from_dict(d) for d in findings_data]
    annotator = AutoAnnotator(gemini_client, repo_path, language)

    count = 0
    for finding in findings:
        if finding.is_duplicate:
            continue
        if finding.annotation != AnnotationStatus.PENDING:
            continue

        status, reason = annotator.annotate_finding(finding)
        finding.annotation = status
        finding.annotation_reason = reason
        count += 1
        log.info(
            f"  [{status.value}] {finding.symbol_name} in {finding.file_path} "
            f"({reason[:60]})"
        )

    # Save back
    updated = [f.to_dict() for f in findings]
    with open(registry_file, "w") as f:
        json.dump(updated, f, indent=2)

    # Update ground truth file
    ground_truth_dir = Path("data/ground_truth")
    ground_truth_dir.mkdir(parents=True, exist_ok=True)

    repo_name = registry_file.stem.replace("_registry", "")
    gt_file = ground_truth_dir / f"{repo_name}.json"

    correct_findings = [f for f in findings if f.annotation == AnnotationStatus.CORRECT and not f.is_duplicate]
    gt_data = {
        "repo": repo_name,
        "violations": [
            {
                "principle": f.principle,
                "file_path": f.file_path,
                "symbol_name": f.symbol_name,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "description": f.description,
            }
            for f in correct_findings
        ],
    }
    with open(gt_file, "w") as f:
        json.dump(gt_data, f, indent=2)

    return count


def auto_annotate_refactorings(
    gemini_client: GeminiClient,
    results_file: Path,
) -> int:
    """Auto-annotate all pending refactoring results for a repo."""
    if not results_file.exists():
        log.error(f"Results file not found: {results_file}")
        return 0

    with open(results_file) as f:
        results_data = json.load(f)

    annotator_client = gemini_client
    count = 0

    for result in results_data:
        if result.get("annotation", "pending") != "pending":
            continue

        # Create a temporary annotator just for the prompt
        prompt = VERIFY_REFACTORING_PROMPT.format(
            principle=result.get("finding", {}).get("principle", ""),
            description=result.get("finding", {}).get("description", ""),
            files_changed=", ".join(result.get("files_changed", [])),
            diff=result.get("patch_diff", "")[:5000],
            tests_passed=result.get("tests_passed", False),
        )

        try:
            response = annotator_client.generate(prompt, temperature=0.1, expect_json=True)
            data = _parse_json_safely(response)
            if data and isinstance(data, dict):
                is_correct = data.get("is_correct", True)
                reason = data.get("reason", "Auto-verified")
                confidence = data.get("confidence", 0.5)

                result["annotation"] = "correct" if is_correct else "incorrect"
                result["annotation_reason"] = f"[Auto, confidence={confidence:.2f}] {reason}"
                count += 1

                finding_name = result.get("finding", {}).get("symbol_name", "?")
                log.info(f"  [{result['annotation']}] {finding_name} ({reason[:60]})")
        except Exception as e:
            log.warning(f"Auto-annotation failed: {e}")

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)

    return count
