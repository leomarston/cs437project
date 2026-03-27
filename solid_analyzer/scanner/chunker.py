"""Split large source files into analyzable chunks."""

import logging
from pathlib import Path

log = logging.getLogger("solid_analyzer")

MAX_CHUNK_LINES = 500


def read_file_content(file_path: Path) -> str:
    """Read file content with encoding fallback."""
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            return file_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def chunk_file(file_path: Path, max_lines: int = MAX_CHUNK_LINES) -> list[dict]:
    """Split a file into chunks suitable for LLM analysis.

    Returns list of dicts with 'content', 'start_line', 'end_line', 'file_path'.
    """
    content = read_file_content(file_path)
    if not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    total = len(lines)

    if total <= max_lines:
        return [{
            "content": content,
            "start_line": 1,
            "end_line": total,
            "file_path": str(file_path),
        }]

    chunks = []
    start = 0
    while start < total:
        end = min(start + max_lines, total)
        # Try to break at a class/function boundary
        if end < total:
            for i in range(end, max(start + max_lines // 2, start), -1):
                line = lines[i].strip() if i < total else ""
                if (line.startswith("class ") or line.startswith("def ") or
                    line.startswith("public ") or line.startswith("private ") or
                    line.startswith("protected ") or line.startswith("fun ") or
                    line == "}"):
                    end = i
                    break

        chunk_content = "".join(lines[start:end])
        chunks.append({
            "content": chunk_content,
            "start_line": start + 1,
            "end_line": end,
            "file_path": str(file_path),
        })
        start = end

    log.debug(f"Split {file_path.name} into {len(chunks)} chunks ({total} lines)")
    return chunks
