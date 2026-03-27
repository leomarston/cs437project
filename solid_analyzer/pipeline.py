"""Main pipeline orchestrator: scan -> detect -> refactor -> report."""

import json
import logging
from pathlib import Path
from typing import Optional

from .config import Config, RepoConfig
from .detector.gemini_client import GeminiClient
from .detector.models import Finding, RefactorResult, ScanReport
from .detector.prompts import build_detection_prompt, PROMPT_VARIANTS
from .detector.response_parser import parse_detection_response
from .detector.deduplicator import IssueRegistry
from .scanner.repo_manager import RepoManager
from .scanner.file_selector import FileSelector
from .scanner.chunker import chunk_file
from .refactorer.refactor_planner import RefactorPlanner
from .refactorer.patch_applier import PatchApplier
from .refactorer.test_runner import TestRunner
from .metrics.code_quality import compute_metrics
from .metrics.evaluation import evaluate_detections, evaluate_refactorings
from .reporter.pr_report import generate_pr_report
from .reporter.summary_report import generate_summary_report, export_findings_csv
from .utils.budget import BudgetTracker

log = logging.getLogger("solid_analyzer")


class Pipeline:
    """Orchestrates the full detection -> refactoring -> validation pipeline."""

    def __init__(self, config: Config):
        self.config = config
        self.gemini = GeminiClient(
            api_key=config.gemini.api_key,
            model=config.gemini.model,
            temperature=config.gemini.temperature,
            max_output_tokens=config.gemini.max_output_tokens,
        )
        self.repo_manager = RepoManager(config.repos_dir)
        self.budget = BudgetTracker(
            budget_file=config.output_dir / "budget_state.json",
            detections_per_principle=config.budget.per_principle,
            refactorings_per_principle=config.budget.per_principle,
        )

    def run_detection(self, repo_config: RepoConfig) -> list[Finding]:
        """Run the full detection pipeline for a single repository.

        Performs 60 detection scans (12 per SOLID principle), varying prompt
        variants and temperatures across scans.
        """
        repo_name = repo_config.name
        language = repo_config.language
        repo_path = self.repo_manager.get_repo_path(repo_name)

        # Initialize registry
        registry = IssueRegistry(self.config.output_dir / "findings" / f"{repo_name}_registry.json")

        # Select files for analysis
        selector = FileSelector(language, repo_config.source_dirs)
        source_files = selector.select_files(repo_path)

        if not source_files:
            log.error(f"No source files found for {repo_name}")
            return []

        log.info(f"Starting detection for {repo_name}: {len(source_files)} files, "
                 f"5 principles x 12 scans = 60 detection attempts")

        all_findings = []
        variant_keys = list(PROMPT_VARIANTS.keys())
        temperatures = [0.1, 0.2, 0.3, 0.4, 0.2, 0.1, 0.3, 0.2, 0.5, 0.1, 0.2, 0.3]

        for principle in self.config.SOLID_PRINCIPLES:
            log.info(f"[{repo_name}] Scanning for {principle} violations...")

            for scan_idx in range(self.config.budget.per_principle):
                if not self.budget.can_detect(repo_name, principle):
                    log.info(f"Detection budget exhausted for {repo_name}/{principle}")
                    break

                scan_id = scan_idx + 1
                variant = variant_keys[scan_idx % len(variant_keys)]
                temp = temperatures[scan_idx % len(temperatures)]

                log.info(f"  Scan {scan_id}/12 for {principle} "
                         f"(variant={variant}, temp={temp})")

                scan_findings = self._run_single_scan(
                    repo_name=repo_name,
                    repo_path=repo_path,
                    language=language,
                    principle=principle,
                    source_files=source_files,
                    scan_id=scan_id,
                    variant=variant,
                    temperature=temp,
                    registry=registry,
                )

                self.budget.record_detection(repo_name, principle)
                all_findings.extend(scan_findings)

                # Save scan report
                report = ScanReport(
                    repo=repo_name,
                    principle=principle,
                    scan_id=scan_id,
                    prompt_variant=variant,
                    temperature=temp,
                    findings=scan_findings,
                    new_findings=sum(1 for f in scan_findings if not f.is_duplicate),
                    duplicate_findings=sum(1 for f in scan_findings if f.is_duplicate),
                )
                self._save_scan_report(report)

        # Export results
        findings_dir = self.config.output_dir / "findings"
        export_findings_csv(all_findings, findings_dir / f"{repo_name}_findings.csv")

        unique = registry.unique_count
        total = registry.total_count
        log.info(f"Detection complete for {repo_name}: {unique} unique findings "
                 f"({total} total including duplicates)")

        return all_findings

    def _run_single_scan(
        self,
        repo_name: str,
        repo_path: Path,
        language: str,
        principle: str,
        source_files: list[Path],
        scan_id: int,
        variant: str,
        temperature: float,
        registry: IssueRegistry,
    ) -> list[Finding]:
        """Run a single detection scan across all source files."""
        scan_findings = []

        for file_path in source_files:
            chunks = chunk_file(file_path)
            rel_path = str(file_path.relative_to(repo_path))

            for chunk in chunks:
                prompt = build_detection_prompt(
                    principle=principle,
                    code=chunk["content"],
                    file_path=rel_path,
                    language=language,
                    start_line=chunk["start_line"],
                    end_line=chunk["end_line"],
                    variant=variant,
                    repo_name=repo_name,
                )

                try:
                    response = self.gemini.generate(prompt, temperature=temperature)
                    findings = parse_detection_response(
                        raw_response=response,
                        repo=repo_name,
                        principle=principle,
                        file_path=rel_path,
                        scan_id=scan_id,
                        chunk_start_line=chunk["start_line"],
                    )

                    for finding in findings:
                        is_new = registry.register(finding)
                        scan_findings.append(finding)
                        if is_new:
                            log.info(f"    NEW: [{finding.severity.value}] {finding.symbol_name} "
                                     f"in {rel_path}:{finding.line_start}")

                except Exception as e:
                    log.error(f"    Error scanning {rel_path}: {e}")

        return scan_findings

    def run_refactoring(self, repo_config: RepoConfig) -> list[RefactorResult]:
        """Run the refactoring pipeline for a repository's detected findings."""
        repo_name = repo_config.name
        language = repo_config.language
        repo_path = self.repo_manager.get_repo_path(repo_name)

        registry = IssueRegistry(self.config.output_dir / "findings" / f"{repo_name}_registry.json")
        results = []

        planner = RefactorPlanner(self.gemini, repo_path, language)
        test_runner = TestRunner(repo_path, repo_config.test_command)

        log.info(f"Starting refactoring for {repo_name}")

        for principle in self.config.SOLID_PRINCIPLES:
            findings = registry.get_unique_findings(repo=repo_name, principle=principle)
            log.info(f"[{repo_name}] Refactoring {principle}: {len(findings)} findings available")

            for finding in findings:
                if not self.budget.can_refactor(repo_name, principle):
                    log.info(f"Refactoring budget exhausted for {repo_name}/{principle}")
                    break

                log.info(f"  Refactoring {finding.symbol_name} in {finding.file_path}")

                # Compute pre-refactoring metrics
                file_path = repo_path / finding.file_path
                metrics_before = {}
                if file_path.exists():
                    m = compute_metrics(file_path, language)
                    metrics_before = m.to_dict()

                # Generate refactoring plan
                plan = planner.plan_refactoring(finding)
                if not plan:
                    log.warning(f"  Failed to generate refactoring plan")
                    self.budget.record_refactoring(repo_name, principle)
                    continue

                # Apply the patch
                applier = PatchApplier(repo_path)
                files_changed = applier.apply_refactoring(plan, finding.issue_id)

                if not files_changed:
                    log.warning(f"  No files changed during refactoring")
                    applier.rollback()
                    self.budget.record_refactoring(repo_name, principle)
                    continue

                # Get the diff
                diff = applier.get_diff()

                # Run tests
                test_result = test_runner.run_tests()

                # Compute post-refactoring metrics
                metrics_after = {}
                if file_path.exists():
                    m = compute_metrics(file_path, language)
                    metrics_after = m.to_dict()

                # Create result
                result = RefactorResult(
                    finding=finding,
                    original_code="",
                    refactored_code=plan.get("explanation", ""),
                    patch_diff=diff,
                    files_changed=files_changed,
                    tests_passed=test_result.passed,
                    test_output=test_result.output[:5000],
                    metrics_before=metrics_before,
                    metrics_after=metrics_after,
                )

                # Commit if tests pass, rollback otherwise
                if test_result.passed:
                    applier.commit_refactoring(
                        finding.issue_id, principle, finding.description[:80]
                    )
                    log.info(f"  Refactoring committed (tests passed)")
                else:
                    applier.rollback()
                    log.warning(f"  Refactoring rolled back (tests failed)")

                applier.return_to_main()

                # Generate PR report
                report_dir = self.config.output_dir / "refactors" / repo_name
                report_path = generate_pr_report(result, report_dir)
                result.pr_report_path = str(report_path)

                results.append(result)
                self.budget.record_refactoring(repo_name, principle)

        # Save refactoring results
        self._save_refactor_results(repo_name, results)

        passed = sum(1 for r in results if r.tests_passed)
        log.info(f"Refactoring complete for {repo_name}: {len(results)} attempts, "
                 f"{passed} passed tests")

        return results

    def run_full_pipeline(self, repo_config: RepoConfig):
        """Run the complete pipeline: detect -> refactor -> report."""
        repo_name = repo_config.name
        log.info(f"{'='*60}")
        log.info(f"Starting full pipeline for: {repo_name}")
        log.info(f"{'='*60}")

        # Clone/update repo
        self.repo_manager.clone_or_update(
            repo_config.url, repo_name, repo_config.branch
        )

        # Detection phase
        findings = self.run_detection(repo_config)

        # Refactoring phase
        results = self.run_refactoring(repo_config)

        # Generate summary report
        budget_summary = self.budget.summary(repo_name)
        generate_summary_report(
            findings=findings,
            refactor_results=results,
            budget_summary=budget_summary,
            output_dir=self.config.output_dir / "reports",
            repo_name=repo_name,
        )

        log.info(f"Pipeline complete for {repo_name}")
        return findings, results

    def generate_report(self, repo_name: str):
        """Generate reports from existing data."""
        findings_file = self.config.output_dir / "findings" / f"{repo_name}_registry.json"
        results_file = self.config.output_dir / "refactors" / f"{repo_name}_results.json"

        findings = []
        if findings_file.exists():
            with open(findings_file) as f:
                findings = [Finding.from_dict(d) for d in json.load(f)]

        results = []
        if results_file.exists():
            with open(results_file) as f:
                data = json.load(f)
            # Results need special handling for nested Finding
            for item in data:
                finding = Finding.from_dict(item["finding"])
                result = RefactorResult(
                    finding=finding,
                    original_code=item.get("original_code", ""),
                    refactored_code=item.get("refactored_code", ""),
                    patch_diff=item.get("patch_diff", ""),
                    files_changed=item.get("files_changed", []),
                    tests_passed=item.get("tests_passed", False),
                    test_output=item.get("test_output", ""),
                    metrics_before=item.get("metrics_before", {}),
                    metrics_after=item.get("metrics_after", {}),
                )
                results.append(result)

        budget_summary = self.budget.summary(repo_name)
        generate_summary_report(
            findings=findings,
            refactor_results=results,
            budget_summary=budget_summary,
            output_dir=self.config.output_dir / "reports",
            repo_name=repo_name,
        )

    def _save_scan_report(self, report: ScanReport):
        scan_dir = self.config.output_dir / "findings" / report.repo / "scans"
        scan_dir.mkdir(parents=True, exist_ok=True)
        path = scan_dir / f"scan_{report.principle}_{report.scan_id}.json"
        with open(path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

    def _save_refactor_results(self, repo_name: str, results: list[RefactorResult]):
        results_dir = self.config.output_dir / "refactors"
        results_dir.mkdir(parents=True, exist_ok=True)
        path = results_dir / f"{repo_name}_results.json"
        with open(path, "w") as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
