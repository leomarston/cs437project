"""Command-line interface for the SOLID Analyzer framework."""

import sys
import json
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from .config import load_config, Config
from .pipeline import Pipeline
from .detector.models import Finding, AnnotationStatus, RefactorResult
from .detector.deduplicator import IssueRegistry
from .utils.logging import setup_logging

console = Console()


@click.group()
@click.option("--config", "config_path", default="data/repos.yaml", help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--output-dir", default="output", help="Output directory")
@click.pass_context
def main(ctx, config_path, verbose, output_dir):
    """SOLID Analyzer - Automated SOLID violation detection and refactoring."""
    setup_logging(verbose=verbose, log_file=f"{output_dir}/solid_analyzer.log")
    config = load_config(config_path)
    config.output_dir = Path(output_dir)
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("repo_name")
@click.pass_context
def detect(ctx, repo_name):
    """Run SOLID violation detection on a repository."""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    repo_config = _find_repo(config, repo_name)
    if not repo_config:
        console.print(f"[red]Repository '{repo_name}' not found in config[/red]")
        sys.exit(1)

    console.print(f"[bold green]Starting detection for {repo_name}...[/bold green]")
    findings = pipeline.run_detection(repo_config)

    unique = sum(1 for f in findings if not f.is_duplicate)
    console.print(f"\n[bold]Detection complete:[/bold] {unique} unique findings "
                  f"({len(findings)} total)")


@main.command()
@click.argument("repo_name")
@click.pass_context
def refactor(ctx, repo_name):
    """Run automated refactoring on detected violations."""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    repo_config = _find_repo(config, repo_name)
    if not repo_config:
        console.print(f"[red]Repository '{repo_name}' not found in config[/red]")
        sys.exit(1)

    console.print(f"[bold green]Starting refactoring for {repo_name}...[/bold green]")
    results = pipeline.run_refactoring(repo_config)

    passed = sum(1 for r in results if r.tests_passed)
    console.print(f"\n[bold]Refactoring complete:[/bold] {len(results)} attempts, "
                  f"{passed} passed tests")


@main.command()
@click.argument("repo_name")
@click.pass_context
def run(ctx, repo_name):
    """Run full pipeline (detect + refactor + report) for a repository."""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    if repo_name == "all":
        for repo_config in config.repositories:
            pipeline.run_full_pipeline(repo_config)
    else:
        repo_config = _find_repo(config, repo_name)
        if not repo_config:
            console.print(f"[red]Repository '{repo_name}' not found in config[/red]")
            sys.exit(1)
        pipeline.run_full_pipeline(repo_config)

    console.print("[bold green]Pipeline complete![/bold green]")


@main.command()
@click.argument("repo_name")
@click.pass_context
def report(ctx, repo_name):
    """Generate reports from existing detection/refactoring data."""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    if repo_name == "all":
        for repo_config in config.repositories:
            pipeline.generate_report(repo_config.name)
    else:
        pipeline.generate_report(repo_name)

    console.print("[bold green]Reports generated![/bold green]")


@main.command()
@click.argument("repo_name")
@click.pass_context
def status(ctx, repo_name):
    """Show budget usage and progress for a repository."""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    if repo_name == "all":
        repos = [rc.name for rc in config.repositories]
    else:
        repos = [repo_name]

    for rname in repos:
        summary = pipeline.budget.summary(rname)
        table = Table(title=f"Budget Status: {rname}")
        table.add_column("Principle")
        table.add_column("Detections", justify="right")
        table.add_column("Refactorings", justify="right")

        for p in config.SOLID_PRINCIPLES:
            det = summary["detections"].get(p, 0)
            ref = summary["refactorings"].get(p, 0)
            table.add_row(p, f"{det}/12", f"{ref}/12")

        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{summary['total_detections']}/60[/bold]",
            f"[bold]{summary['total_refactorings']}/60[/bold]",
        )
        console.print(table)


@main.command()
@click.argument("repo_name")
@click.pass_context
def clone(ctx, repo_name):
    """Clone or update a target repository."""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    if repo_name == "all":
        for repo_config in config.repositories:
            pipeline.repo_manager.clone_or_update(
                repo_config.url, repo_config.name, repo_config.branch
            )
    else:
        repo_config = _find_repo(config, repo_name)
        if not repo_config:
            console.print(f"[red]Repository '{repo_name}' not found in config[/red]")
            sys.exit(1)
        pipeline.repo_manager.clone_or_update(
            repo_config.url, repo_config.name, repo_config.branch
        )

    console.print("[bold green]Repository ready![/bold green]")


@main.command()
@click.argument("repo_name")
@click.option("--type", "annotation_type", type=click.Choice(["detections", "refactorings"]),
              default="detections", help="What to annotate")
@click.pass_context
def annotate(ctx, repo_name, annotation_type):
    """Interactively annotate findings/refactorings as correct or incorrect (ground truth).

    This is MANDATORY for computing precision, recall, and F1 scores.
    """
    config = ctx.obj["config"]
    output_dir = config.output_dir

    if annotation_type == "detections":
        _annotate_detections(output_dir, repo_name)
    else:
        _annotate_refactorings(output_dir, repo_name)


def _annotate_detections(output_dir: Path, repo_name: str):
    """Interactive annotation of detection findings."""
    registry_file = output_dir / "findings" / f"{repo_name}_registry.json"
    if not registry_file.exists():
        console.print(f"[red]No findings found for {repo_name}. Run detection first.[/red]")
        return

    with open(registry_file) as f:
        findings_data = json.load(f)

    findings = [Finding.from_dict(d) for d in findings_data]
    unique = [f for f in findings if not f.is_duplicate]
    pending = [f for f in unique if f.annotation == AnnotationStatus.PENDING]

    console.print(f"\n[bold]Annotating detections for {repo_name}[/bold]")
    console.print(f"Total unique findings: {len(unique)}, Pending: {len(pending)}")
    console.print("---")

    annotated_count = 0
    for i, finding in enumerate(pending):
        console.print(f"\n[bold cyan]Finding {i + 1}/{len(pending)}[/bold cyan]")
        console.print(f"  Issue ID: {finding.issue_id}")
        console.print(f"  Principle: [yellow]{finding.principle}[/yellow]")
        console.print(f"  File: {finding.file_path}:{finding.line_start}-{finding.line_end}")
        console.print(f"  Symbol: {finding.symbol_name}")
        console.print(f"  Severity: {finding.severity.value}")
        console.print(f"  Description: {finding.description}")
        console.print(f"  Reasoning: {finding.reasoning}")
        console.print(f"  Suggested Fix: {finding.suggested_fix}")

        choice = Prompt.ask(
            "\nIs this a correct violation?",
            choices=["y", "n", "s", "q"],
            default="s",
        )

        if choice == "q":
            console.print("Stopping annotation.")
            break
        elif choice == "s":
            continue
        elif choice == "y":
            reason = Prompt.ask("Brief reason why it's correct", default="Confirmed violation")
            finding.annotation = AnnotationStatus.CORRECT
            finding.annotation_reason = reason
            annotated_count += 1
        elif choice == "n":
            reason = Prompt.ask("Brief reason why it's incorrect", default="Not a real violation")
            finding.annotation = AnnotationStatus.INCORRECT
            finding.annotation_reason = reason
            annotated_count += 1

    # Save back
    # Update the original findings_data with annotations
    findings_by_id = {f.issue_id: f for f in findings}
    for f in pending:
        if f.annotation != AnnotationStatus.PENDING:
            findings_by_id[f.issue_id] = f

    updated = [findings_by_id.get(f.issue_id, f).to_dict()
               for f in findings]

    with open(registry_file, "w") as f_out:
        json.dump(updated, f_out, indent=2)

    # Also update ground truth file
    ground_truth_dir = Path("data/ground_truth")
    ground_truth_dir.mkdir(parents=True, exist_ok=True)
    gt_file = ground_truth_dir / f"{repo_name}.json"

    correct_findings = [f for f in findings_by_id.values()
                       if f.annotation == AnnotationStatus.CORRECT]
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
    with open(gt_file, "w") as f_out:
        json.dump(gt_data, f_out, indent=2)

    console.print(f"\n[bold green]Annotated {annotated_count} findings.[/bold green]")
    _print_annotation_stats(findings_by_id.values())


def _annotate_refactorings(output_dir: Path, repo_name: str):
    """Interactive annotation of refactoring results."""
    results_file = output_dir / "refactors" / f"{repo_name}_results.json"
    if not results_file.exists():
        console.print(f"[red]No refactoring results found for {repo_name}. Run refactoring first.[/red]")
        return

    with open(results_file) as f:
        results_data = json.load(f)

    console.print(f"\n[bold]Annotating refactorings for {repo_name}[/bold]")
    console.print(f"Total refactorings: {len(results_data)}")
    console.print("---")

    annotated_count = 0
    for i, result in enumerate(results_data):
        if result.get("annotation", "pending") != "pending":
            continue

        finding = result["finding"]
        console.print(f"\n[bold cyan]Refactoring {i + 1}/{len(results_data)}[/bold cyan]")
        console.print(f"  Principle: [yellow]{finding['principle']}[/yellow]")
        console.print(f"  File: {finding['file_path']}")
        console.print(f"  Symbol: {finding['symbol_name']}")
        console.print(f"  Description: {finding['description']}")
        console.print(f"  Tests: {'PASSED' if result['tests_passed'] else 'FAILED'}")
        console.print(f"  Files changed: {', '.join(result.get('files_changed', []))}")

        # Show metrics comparison
        if result.get("metrics_before") and result.get("metrics_after"):
            console.print("  Metrics:")
            for key in result["metrics_before"]:
                before = result["metrics_before"].get(key, "N/A")
                after = result["metrics_after"].get(key, "N/A")
                if before != after:
                    console.print(f"    {key}: {before} -> {after}")

        # Show diff (truncated)
        diff = result.get("patch_diff", "")
        if diff:
            console.print(f"\n  Diff (first 500 chars):\n{diff[:500]}")

        choice = Prompt.ask(
            "\nIs this refactoring correct?",
            choices=["y", "n", "s", "q"],
            default="s",
        )

        if choice == "q":
            break
        elif choice == "s":
            continue
        elif choice == "y":
            reason = Prompt.ask("Brief reason", default="Correct refactoring")
            result["annotation"] = "correct"
            result["annotation_reason"] = reason
            annotated_count += 1
        elif choice == "n":
            reason = Prompt.ask("Brief reason", default="Incorrect refactoring")
            result["annotation"] = "incorrect"
            result["annotation_reason"] = reason
            annotated_count += 1

    with open(results_file, "w") as f_out:
        json.dump(results_data, f_out, indent=2)

    console.print(f"\n[bold green]Annotated {annotated_count} refactorings.[/bold green]")


def _print_annotation_stats(findings):
    """Print annotation statistics."""
    total = 0
    correct = 0
    incorrect = 0
    pending = 0
    for f in findings:
        if f.is_duplicate:
            continue
        total += 1
        if f.annotation == AnnotationStatus.CORRECT:
            correct += 1
        elif f.annotation == AnnotationStatus.INCORRECT:
            incorrect += 1
        else:
            pending += 1

    console.print(f"\n[bold]Annotation Stats:[/bold]")
    console.print(f"  Correct (TP): {correct}")
    console.print(f"  Incorrect (FP): {incorrect}")
    console.print(f"  Pending: {pending}")
    if correct + incorrect > 0:
        precision = correct / (correct + incorrect)
        console.print(f"  Precision: {precision:.4f}")


@main.command()
@click.argument("repo_name")
@click.option("--principle", "-p", default=None, help="Specific principle to seed for")
@click.option("--count", "-n", default=5, help="Number of violations to seed per principle")
@click.pass_context
def seed(ctx, repo_name, principle, count):
    """Seed (inject) SOLID violations into a repository for detection/refactoring.

    Use when a repository is 'too clean' to meet the 60/60 budget quotas.
    Violations are injected into copies of source files and documented.
    """
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    repo_config = _find_repo(config, repo_name)
    if not repo_config:
        console.print(f"[red]Repository '{repo_name}' not found in config[/red]")
        sys.exit(1)

    principles = [principle] if principle else config.SOLID_PRINCIPLES

    console.print(f"[bold green]Seeding violations into {repo_name}...[/bold green]")

    from .seeder import ViolationSeeder
    seeder = ViolationSeeder(pipeline.gemini, config.repos_dir / repo_name, repo_config.language)

    total_seeded = 0
    seed_log = []

    for p in principles:
        console.print(f"\n[yellow]Seeding {count} {p} violations...[/yellow]")
        results = seeder.seed_violations(p, count)
        total_seeded += len(results)
        seed_log.extend(results)

        for r in results:
            console.print(f"  Seeded: {r['file_path']} - {r['description']}")

    # Save seed log
    seed_dir = config.output_dir / "seeds"
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed_file = seed_dir / f"{repo_name}_seeds.json"
    with open(seed_file, "w") as f:
        json.dump(seed_log, f, indent=2)

    console.print(f"\n[bold green]Seeded {total_seeded} violations. Log saved to {seed_file}[/bold green]")


def _find_repo(config: Config, name: str):
    for repo in config.repositories:
        if repo.name == name:
            return repo
    return None


if __name__ == "__main__":
    main()
