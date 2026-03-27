"""Automated test suite execution for target repositories."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("solid_analyzer")


@dataclass
class TestResult:
    passed: bool
    output: str
    return_code: int
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    error_message: str = ""


class TestRunner:
    """Runs test suites for target repositories."""

    def __init__(self, repo_path: Path, test_command: str, timeout: int = 600):
        self.repo_path = repo_path
        self.test_command = test_command
        self.timeout = timeout

    def run_tests(self) -> TestResult:
        """Execute the test suite and return results."""
        log.info(f"Running tests: {self.test_command} in {self.repo_path.name}")

        try:
            result = subprocess.run(
                self.test_command,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            output = result.stdout + "\n" + result.stderr
            passed = result.returncode == 0

            test_result = TestResult(
                passed=passed,
                output=output,
                return_code=result.returncode,
            )

            # Try to parse test counts from output
            self._parse_test_counts(test_result, output)

            status = "PASSED" if passed else "FAILED"
            log.info(f"Tests {status} (return code: {result.returncode})")
            return test_result

        except subprocess.TimeoutExpired:
            log.error(f"Tests timed out after {self.timeout}s")
            return TestResult(
                passed=False,
                output="",
                return_code=-1,
                error_message=f"Test execution timed out after {self.timeout}s",
            )
        except Exception as e:
            log.error(f"Failed to run tests: {e}")
            return TestResult(
                passed=False,
                output="",
                return_code=-1,
                error_message=str(e),
            )

    def _parse_test_counts(self, result: TestResult, output: str):
        """Try to extract test counts from output (best effort)."""
        import re

        # pytest style: "X passed, Y failed"
        m = re.search(r"(\d+) passed", output)
        if m:
            result.tests_passed = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            result.tests_failed = int(m.group(1))

        # JUnit/Maven style: "Tests run: X, Failures: Y, Errors: Z"
        m = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+)", output)
        if m:
            result.tests_run = int(m.group(1))
            result.tests_failed = int(m.group(2))
            result.tests_passed = result.tests_run - result.tests_failed

        # Gradle style: "X tests completed, Y failed"
        m = re.search(r"(\d+) tests? completed", output)
        if m:
            result.tests_run = int(m.group(1))

        if result.tests_run == 0:
            result.tests_run = result.tests_passed + result.tests_failed
