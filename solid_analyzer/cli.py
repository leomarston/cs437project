"""Command-line interface for the SOLID Analyzer framework."""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from .config import load_config, Config
from .pipeline import Pipeline
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


def _find_repo(config: Config, name: str):
    for repo in config.repositories:
        if repo.name == name:
            return repo
    return None


if __name__ == "__main__":
    main()
