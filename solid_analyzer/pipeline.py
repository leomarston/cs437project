"""Main pipeline orchestrator: scan -> detect -> refactor -> report."""

import json
import logging
import random
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
from .scanner.chunker import chunk_file, read_file_content
from .refactorer.refactor_planner import RefactorPlanner
from .refactorer.patch_applier import PatchApplier
from .refactorer.test_runner import TestRunner
from .metrics.code_quality import compute_metrics
from .metrics.evaluation import evaluate_detections, evaluate_refactorings
from .reporter.pr_report import generate_pr_report
from .reporter.summary_report import generate_summary_report, export_findings_csv
from .utils.budget import BudgetTracker

log = logging.getLogger("solid_analyzer")

# Max characters to include in a single prompt (leave room for prompt template)
MAX_CODE_CHARS_PER_PROMPT = 15000


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

    # ──────────────────────────────────────────────
    # DETECTION
    # ──────────────────────────────────────────────

    def run_detection(self, repo_config: RepoConfig) -> list[Finding]:
        """Run the full detection pipeline for a single repository.

        Performs 60 detection scans (12 per SOLID principle), varying prompt
        variants and temperatures across scans.  Each scan sends batched
        files to Gemini so we cover the whole repo with reasonable API usage.
        """
        repo_name = repo_config.name
        language = repo_config.language
        repo_path = self.repo_manager.get_repo_path(repo_name)

        registry = IssueRegistry(
            self.config.output_dir / "findings" / f"{repo_name}_registry.json"
        )

        selector = FileSelector(language, repo_config.source_dirs)
        source_files = selector.select_files(repo_path)

        if not source_files:
            log.error(f"No source files found for {repo_name}")
            return []

        log.info(
            f"Starting detection for {repo_name}: {len(source_files)} files, "
            f"5 principles x 12 scans = 60 detection attempts"
        )

        # Pre-chunk all files once
        file_chunks = []
        for fp in source_files:
            rel = str(fp.relative_to(repo_path))
            for ch in chunk_file(fp):
                ch["rel_path"] = rel
                file_chunks.append(ch)

        log.info(f"Total code chunks: {len(file_chunks)}")

        all_findings: list[Finding] = []
        variant_keys = list(PROMPT_VARIANTS.keys())
        temperatures = [0.1, 0.2, 0.3, 0.4, 0.2, 0.1, 0.3, 0.2, 0.5, 0.1, 0.2, 0.3]

        for principle in self.config.SOLID_PRINCIPLES:
            log.info(f"[{repo_name}] Scanning for {principle} violations...")

            # Distribute chunks across 12 scans so every scan covers different files
            shuffled = list(file_chunks)
            random.shuffle(shuffled)
            scans_per_principle = self.config.budget.per_principle  # 12
            batches = _distribute(shuffled, scans_per_principle)

            for scan_idx in range(scans_per_principle):
                if not self.budget.can_detect(repo_name, principle):
                    log.info(f"Detection budget exhausted for {repo_name}/{principle}")
                    break

                scan_id = scan_idx + 1
                variant = variant_keys[scan_idx % len(variant_keys)]
                temp = temperatures[scan_idx % len(temperatures)]
                batch = batches[scan_idx] if scan_idx < len(batches) else []

                log.info(
                    f"  Scan {scan_id}/12 for {principle} "
                    f"(variant={variant}, temp={temp}, chunks={len(batch)})"
                )

                scan_findings = self._run_single_scan(
                    repo_name=repo_name,
                    language=language,
                    principle=principle,
                    chunks=batch,
                    scan_id=scan_id,
                    variant=variant,
                    temperature=temp,
                    registry=registry,
                )

                self.budget.record_detection(repo_name, principle)
                all_findings.extend(scan_findings)

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

        findings_dir = self.config.output_dir / "findings"
        export_findings_csv(all_findings, findings_dir / f"{repo_name}_findings.csv")

        unique = registry.unique_count
        total = registry.total_count
        log.info(
            f"Detection complete for {repo_name}: {unique} unique findings "
            f"({total} total including duplicates)"
        )
        return all_findings

    def _run_single_scan(
        self,
        repo_name: str,
        language: str,
        principle: str,
        chunks: list[dict],
        scan_id: int,
        variant: str,
        temperature: float,
        registry: IssueRegistry,
    ) -> list[Finding]:
        """Run one detection scan by batching code chunks into API calls."""
        scan_findings: list[Finding] = []

        # Group chunks into prompt-sized batches
        prompt_batches = _batch_chunks(chunks, MAX_CODE_CHARS_PER_PROMPT)

        for batch in prompt_batches:
            combined_code, file_map = _combine_chunks(batch)
            # Use the first file as representative for the prompt
            first = batch[0]

            prompt = build_detection_prompt(
                principle=principle,
                code=combined_code,
                file_path=file_map,
                language=language,
                start_line=1,
                end_line=sum(c["end_line"] - c["start_line"] + 1 for c in batch),
                variant=variant,
                repo_name=repo_name,
            )

            try:
                response = self.gemini.generate(prompt, temperature=temperature)
                findings = parse_detection_response(
                    raw_response=response,
                    repo=repo_name,
                    principle=principle,
                    file_path=first["rel_path"],
                    scan_id=scan_id,
                )

                for finding in findings:
                    # Try to match finding file_path to actual files in batch
                    _resolve_file_path(finding, batch)
                    is_new = registry.register(finding)
                    scan_findings.append(finding)
                    if is_new:
                        log.info(
                            f"    NEW: [{finding.severity.value}] "
                            f"{finding.symbol_name} in {finding.file_path}:{finding.line_start}"
                        )

            except Exception as e:
                log.error(f"    Error in scan batch: {e}")

        return scan_findings

    # ──────────────────────────────────────────────
    # REFACTORING
    # ──────────────────────────────────────────────

    def run_refactoring(self, repo_config: RepoConfig) -> list[RefactorResult]:
        """Run the refactoring pipeline for a repository's detected findings."""
        repo_name = repo_config.name
        language = repo_config.language
        repo_path = self.repo_manager.get_repo_path(repo_name)

        registry = IssueRegistry(
            self.config.output_dir / "findings" / f"{repo_name}_registry.json"
        )
        results: list[RefactorResult] = []

        planner = RefactorPlanner(self.gemini, repo_path, language)
        test_runner = TestRunner(repo_path, repo_config.test_command)

        log.info(f"Starting refactoring for {repo_name}")

        for principle in self.config.SOLID_PRINCIPLES:
            findings = registry.get_unique_findings(repo=repo_name, principle=principle)
            log.info(
                f"[{repo_name}] Refactoring {principle}: "
                f"{len(findings)} unique findings available"
            )

            refactor_count = 0
            for finding in findings:
                if not self.budget.can_refactor(repo_name, principle):
                    log.info(f"Refactoring budget exhausted for {repo_name}/{principle}")
                    break

                refactor_count += 1
                log.info(
                    f"  [{principle} {refactor_count}] Refactoring "
                    f"{finding.symbol_name} in {finding.file_path}"
                )

                result = self._refactor_single(
                    finding, repo_path, language, planner, test_runner
                )
                if result:
                    # Generate PR report
                    report_dir = self.config.output_dir / "refactors" / repo_name
                    report_path = generate_pr_report(result, report_dir)
                    result.pr_report_path = str(report_path)
                    results.append(result)

                self.budget.record_refactoring(repo_name, principle)

        self._save_refactor_results(repo_name, results)

        passed = sum(1 for r in results if r.tests_passed)
        log.info(
            f"Refactoring complete for {repo_name}: {len(results)} attempts, "
            f"{passed} passed tests"
        )
        return results

    def _refactor_single(
        self,
        finding: Finding,
        repo_path: Path,
        language: str,
        planner: RefactorPlanner,
        test_runner: TestRunner,
    ) -> Optional[RefactorResult]:
        """Refactor a single finding: plan -> apply -> test -> commit/rollback."""
        file_path = repo_path / finding.file_path

        # Pre-refactoring metrics
        metrics_before = {}
        if file_path.exists():
            metrics_before = compute_metrics(file_path, language).to_dict()

        # Read original code for the report
        original_code = ""
        if file_path.exists():
            original_code = read_file_content(file_path)

        # Generate refactoring plan
        plan = planner.plan_refactoring(finding)
        if not plan:
            log.warning("  Failed to generate refactoring plan")
            return RefactorResult(
                finding=finding,
                original_code=original_code[:3000],
                refactored_code="",
                patch_diff="",
                files_changed=[],
                tests_passed=False,
                test_output="Refactoring plan generation failed",
            )

        # Apply the patch
        applier = PatchApplier(repo_path)
        files_changed = applier.apply_refactoring(plan, finding.issue_id)

        if not files_changed:
            log.warning("  No files changed during refactoring")
            applier.rollback()
            return RefactorResult(
                finding=finding,
                original_code=original_code[:3000],
                refactored_code=plan.get("explanation", ""),
                patch_diff="",
                files_changed=[],
                tests_passed=False,
                test_output="No files were changed",
            )

        # Get diff before tests
        diff = applier.get_diff()

        # Run tests
        test_result = test_runner.run_tests()

        # Post-refactoring metrics
        metrics_after = {}
        if file_path.exists():
            metrics_after = compute_metrics(file_path, language).to_dict()

        result = RefactorResult(
            finding=finding,
            original_code=original_code[:3000],
            refactored_code=plan.get("explanation", ""),
            patch_diff=diff,
            files_changed=files_changed,
            tests_passed=test_result.passed,
            test_output=test_result.output[:5000],
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )

        if test_result.passed:
            applier.commit_refactoring(
                finding.issue_id, finding.principle, finding.description[:80]
            )
            log.info("  Refactoring committed (tests passed)")
        else:
            applier.rollback()
            log.warning("  Refactoring rolled back (tests failed)")

        applier.return_to_main()
        return result

    # ──────────────────────────────────────────────
    # FULL PIPELINE & REPORTING
    # ──────────────────────────────────────────────

    def run_full_pipeline(self, repo_config: RepoConfig):
        """Run the complete pipeline: detect -> refactor -> report."""
        repo_name = repo_config.name
        log.info(f"{'=' * 60}")
        log.info(f"Starting full pipeline for: {repo_name}")
        log.info(f"{'=' * 60}")

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


# ──────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────


def _distribute(items: list, n: int) -> list[list]:
    """Distribute items into n roughly equal groups."""
    groups: list[list] = [[] for _ in range(n)]
    for i, item in enumerate(items):
        groups[i % n].append(item)
    return groups


def _batch_chunks(chunks: list[dict], max_chars: int) -> list[list[dict]]:
    """Group chunks into batches that fit within max_chars of code content."""
    batches: list[list[dict]] = []
    current_batch: list[dict] = []
    current_size = 0

    for chunk in chunks:
        size = len(chunk.get("content", ""))
        if current_size + size > max_chars and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0
        current_batch.append(chunk)
        current_size += size

    if current_batch:
        batches.append(current_batch)

    return batches


def _combine_chunks(chunks: list[dict]) -> tuple[str, str]:
    """Combine multiple chunks into a single code block with file headers."""
    parts = []
    files = set()
    for chunk in chunks:
        rel = chunk.get("rel_path", chunk.get("file_path", "unknown"))
        files.add(rel)
        parts.append(f"// === FILE: {rel} (lines {chunk['start_line']}-{chunk['end_line']}) ===")
        parts.append(chunk["content"])
        parts.append("")

    file_map = ", ".join(sorted(files))
    return "\n".join(parts), file_map


def _resolve_file_path(finding: Finding, chunks: list[dict]):
    """Try to match a finding's file path to one of the batch's actual file paths."""
    # If the LLM returned a file path that matches one in the batch, use it
    rel_paths = {c.get("rel_path", "") for c in chunks}
    if finding.file_path in rel_paths:
        return

    # Try partial matching
    for rel in rel_paths:
        if rel.endswith(finding.file_path) or finding.file_path.endswith(rel):
            finding.file_path = rel
            return

    # If only one file in batch, assign it
    if len(rel_paths) == 1:
        finding.file_path = next(iter(rel_paths))
