"""Parse and validate Gemini API responses into Finding objects."""

import json
import logging
from typing import Optional

from .models import Finding, Severity

log = logging.getLogger("solid_analyzer")


def parse_detection_response(
    raw_response: str | dict | list,
    repo: str,
    principle: str,
    file_path: str,
    scan_id: int,
    chunk_start_line: int = 0,
) -> list[Finding]:
    """Parse a Gemini detection response into Finding objects."""
    if isinstance(raw_response, str):
        data = _parse_json_safely(raw_response)
    else:
        data = raw_response

    if data is None:
        log.warning(f"Could not parse response for {file_path}")
        return []

    if isinstance(data, dict):
        # Some responses wrap findings in a key
        if "violations" in data:
            data = data["violations"]
        elif "findings" in data:
            data = data["findings"]
        else:
            data = [data]

    if not isinstance(data, list):
        log.warning(f"Unexpected response format for {file_path}: {type(data)}")
        return []

    findings = []
    for item in data:
        finding = _parse_single_finding(item, repo, principle, file_path, scan_id, chunk_start_line)
        if finding:
            findings.append(finding)

    return findings


def _parse_json_safely(text: str) -> Optional[dict | list]:
    """Attempt to parse JSON from potentially messy LLM output."""
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array or object in the text
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    log.warning(f"Failed to parse JSON from response: {text[:200]}...")
    return None


def _parse_single_finding(
    item: dict,
    repo: str,
    principle: str,
    file_path: str,
    scan_id: int,
    chunk_start_line: int,
) -> Optional[Finding]:
    """Parse a single finding dict into a Finding object."""
    if not isinstance(item, dict):
        return None

    try:
        symbol = item.get("symbol_name", item.get("symbol", item.get("class_name", "unknown")))
        line_start = int(item.get("line_start", item.get("start_line", 0)))
        line_end = int(item.get("line_end", item.get("end_line", line_start)))

        # Adjust for chunk offset
        if chunk_start_line > 1:
            line_start += chunk_start_line - 1
            line_end += chunk_start_line - 1

        severity_str = item.get("severity", "medium").lower()
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.MEDIUM

        return Finding(
            repo=repo,
            principle=principle,
            file_path=file_path,
            symbol_name=str(symbol),
            line_start=line_start,
            line_end=line_end,
            description=str(item.get("description", "")),
            reasoning=str(item.get("reasoning", "")),
            severity=severity,
            suggested_fix=str(item.get("suggested_fix", "")),
            scan_id=scan_id,
        )
    except (ValueError, TypeError, KeyError) as e:
        log.warning(f"Failed to parse finding: {e}")
        return None


def parse_refactoring_response(raw_response: str | dict) -> Optional[dict]:
    """Parse a Gemini refactoring response."""
    if isinstance(raw_response, str):
        data = _parse_json_safely(raw_response)
    else:
        data = raw_response

    if data is None or not isinstance(data, dict):
        return None

    if "refactored_files" not in data:
        # Try to find it nested
        if "response" in data and isinstance(data["response"], dict):
            data = data["response"]

    if "refactored_files" not in data:
        log.warning("Refactoring response missing 'refactored_files' key")
        return None

    return data
