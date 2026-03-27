"""Code quality metrics computation (cyclomatic complexity, etc.)."""

import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field

log = logging.getLogger("solid_analyzer")


@dataclass
class QualityMetrics:
    file_path: str = ""
    cyclomatic_complexity: float = 0.0
    lines_of_code: int = 0
    num_classes: int = 0
    num_methods: int = 0
    avg_method_length: float = 0.0
    max_method_length: int = 0
    import_count: int = 0
    comment_ratio: float = 0.0
    raw_details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "lines_of_code": self.lines_of_code,
            "num_classes": self.num_classes,
            "num_methods": self.num_methods,
            "avg_method_length": self.avg_method_length,
            "max_method_length": self.max_method_length,
            "import_count": self.import_count,
            "comment_ratio": self.comment_ratio,
        }


def compute_python_metrics(file_path: Path) -> QualityMetrics:
    """Compute code quality metrics for a Python file using radon."""
    metrics = QualityMetrics(file_path=str(file_path))

    try:
        content = file_path.read_text(errors="ignore")
        lines = content.splitlines()
        metrics.lines_of_code = len([l for l in lines if l.strip()])

        # Count classes, methods, imports
        metrics.num_classes = sum(1 for l in lines if l.strip().startswith("class "))
        metrics.num_methods = sum(1 for l in lines if l.strip().startswith("def "))
        metrics.import_count = sum(1 for l in lines if l.strip().startswith(("import ", "from ")))

        # Comment ratio
        comment_lines = sum(1 for l in lines if l.strip().startswith("#"))
        if metrics.lines_of_code > 0:
            metrics.comment_ratio = comment_lines / metrics.lines_of_code

        # Method lengths
        method_lengths = _compute_method_lengths(lines, "def ")
        if method_lengths:
            metrics.avg_method_length = sum(method_lengths) / len(method_lengths)
            metrics.max_method_length = max(method_lengths)

        # Cyclomatic complexity via radon
        try:
            result = subprocess.run(
                ["python", "-m", "radon", "cc", str(file_path), "-a", "-j"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                if str(file_path) in data:
                    blocks = data[str(file_path)]
                    if blocks:
                        total_cc = sum(b.get("complexity", 0) for b in blocks)
                        metrics.cyclomatic_complexity = total_cc / len(blocks)
        except Exception:
            pass

    except Exception as e:
        log.warning(f"Error computing metrics for {file_path}: {e}")

    return metrics


def compute_java_kotlin_metrics(file_path: Path) -> QualityMetrics:
    """Compute basic code quality metrics for Java/Kotlin files."""
    metrics = QualityMetrics(file_path=str(file_path))

    try:
        content = file_path.read_text(errors="ignore")
        lines = content.splitlines()
        metrics.lines_of_code = len([l for l in lines if l.strip() and not l.strip().startswith("//")])

        # Count classes and methods
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in ["class ", "public class ", "abstract class ",
                                                       "interface ", "public interface "]):
                metrics.num_classes += 1
            if any(kw in stripped for kw in ["public ", "private ", "protected ", "fun "]) and "(" in stripped:
                if not stripped.startswith("//") and not stripped.startswith("*"):
                    metrics.num_methods += 1

        # Imports
        metrics.import_count = sum(1 for l in lines if l.strip().startswith("import "))

        # Comment ratio
        comment_lines = sum(1 for l in lines if l.strip().startswith(("//", "*", "/*")))
        if metrics.lines_of_code > 0:
            metrics.comment_ratio = comment_lines / metrics.lines_of_code

        # Method lengths (heuristic: count lines between method signatures)
        method_starts = ["public ", "private ", "protected ", "fun "]
        method_lengths = []
        current_length = 0
        in_method = False
        brace_depth = 0
        for line in lines:
            stripped = line.strip()
            if any(kw in stripped for kw in method_starts) and "(" in stripped and not stripped.startswith(("//", "*")):
                if in_method and current_length > 0:
                    method_lengths.append(current_length)
                in_method = True
                current_length = 0
                brace_depth = 0
            if in_method:
                current_length += 1
                brace_depth += stripped.count("{") - stripped.count("}")
                if brace_depth <= 0 and current_length > 1 and "}" in stripped:
                    method_lengths.append(current_length)
                    in_method = False
                    current_length = 0

        if method_lengths:
            metrics.avg_method_length = sum(method_lengths) / len(method_lengths)
            metrics.max_method_length = max(method_lengths)

        # Approximate cyclomatic complexity (count decision points)
        decision_keywords = ["if ", "else if ", "elif ", "for ", "while ", "case ",
                            "catch ", "&&", "||", "?"]
        decisions = sum(
            sum(1 for kw in decision_keywords if kw in line)
            for line in lines if not line.strip().startswith(("//", "*"))
        )
        if metrics.num_methods > 0:
            metrics.cyclomatic_complexity = (decisions + metrics.num_methods) / metrics.num_methods

    except Exception as e:
        log.warning(f"Error computing metrics for {file_path}: {e}")

    return metrics


def compute_metrics(file_path: Path, language: str) -> QualityMetrics:
    """Compute quality metrics based on language."""
    if language == "python":
        return compute_python_metrics(file_path)
    return compute_java_kotlin_metrics(file_path)


def _compute_method_lengths(lines: list[str], keyword: str) -> list[int]:
    """Compute method lengths for indentation-based languages."""
    method_lengths = []
    current_length = 0
    in_method = False
    method_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_method:
                current_length += 1
            continue

        indent = len(line) - len(line.lstrip())

        if stripped.startswith(keyword):
            if in_method and current_length > 0:
                method_lengths.append(current_length)
            in_method = True
            method_indent = indent
            current_length = 1
        elif in_method:
            if indent > method_indent or not stripped:
                current_length += 1
            else:
                method_lengths.append(current_length)
                in_method = False
                current_length = 0

    if in_method and current_length > 0:
        method_lengths.append(current_length)

    return method_lengths
