"""Ralph review command - run the review loop with automatic configuration.

This module implements the 'ralph review' command which automatically
detects and configures reviewers on first run, then executes the review loop.
"""

import logging
from pathlib import Path

import typer

from ralph.models import load_reviewer_configs
from ralph.services import (
    ReviewerResult,
    ReviewLoopService,
    detect_languages,
    detect_reviewers,
    has_reviewer_config,
    write_reviewer_config,
)
from ralph.utils import (
    console,
    print_error,
    print_review_step,
    print_success,
)

logger = logging.getLogger(__name__)


_DETECTION_REASONS: dict[str, str] = {
    "code-simplifier": "universal reviewer (included for all projects)",
    "repo-structure": "universal reviewer (included for all projects)",
    "python-code": "found .py files",
    "bicep": "found .bicep files",
    "github-actions": "found .github/workflows/*.yml files",
    "test-quality": "found test_*.py or *_test.py files",
    "release": "found CHANGELOG.md",
}


def _get_detection_reason(reviewer_name: str) -> str:
    """Get the detection reason for a reviewer.

    Args:
        reviewer_name: Name of the reviewer.

    Returns:
        Human-readable reason for why the reviewer was detected.
    """
    return _DETECTION_REASONS.get(reviewer_name, "detected in project")


def review(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full JSON output"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warning-level reviewers as blocking",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-detect and update reviewer configuration",
    ),
    no_fix: bool = typer.Option(
        False,
        "--no-fix",
        help="Report review findings without applying automated fixes",
    ),
) -> None:
    """Run the review loop with automatic configuration.

    On first run (no existing config): detects reviewers based on project
    contents, writes configuration to CLAUDE.md, then executes the review loop.

    On subsequent runs: uses existing configuration from CLAUDE.md.

    With --force: re-detects reviewers, shows what changed, and overwrites
    the existing configuration before running the review loop.
    """
    project_root = Path.cwd()
    claude_md_path = project_root / "CLAUDE.md"
    progress_path = project_root / "plans" / "PROGRESS.txt"

    console.print("[bold]Ralph Review[/bold]")
    console.print()

    has_config = has_reviewer_config(claude_md_path)

    if force and has_config:
        console.print("[dim]Force mode - re-detecting reviewers...[/dim]")
        console.print()

        old_reviewers = load_reviewer_configs(claude_md_path)
        old_names = {r.name for r in old_reviewers}

        reviewers = detect_reviewers(project_root)
        new_names = {r.name for r in reviewers}

        added_names = sorted(new_names - old_names)
        removed_names = sorted(old_names - new_names)

        if added_names or removed_names:
            console.print("[bold]Configuration Changes:[/bold]")
            for name in added_names:
                reason = _get_detection_reason(name)
                console.print(f"  [green]+ {name}[/green] ({reason})")
            for name in removed_names:
                console.print(f"  [red]- {name}[/red]")
            console.print()
        else:
            console.print("[dim]No changes detected - configuration is up to date[/dim]")
            console.print()

        write_reviewer_config(claude_md_path, reviewers)
        console.print(f"[dim]Configuration updated in {claude_md_path}[/dim]")
        console.print()
    elif not has_config:
        console.print("[dim]First run detected - configuring reviewers...[/dim]")
        console.print()

        reviewers = detect_reviewers(project_root)

        console.print("[bold]Detected Reviewers:[/bold]")
        for reviewer in reviewers:
            reason = _get_detection_reason(reviewer.name)
            console.print(f"  [green]+[/green] {reviewer.name} ({reason})")

        console.print()

        write_reviewer_config(claude_md_path, reviewers)
        console.print(f"[dim]Configuration written to {claude_md_path}[/dim]")
        console.print()
    else:
        console.print("[dim]Using existing reviewer configuration[/dim]")
        console.print()

        reviewers = load_reviewer_configs(claude_md_path)

        suggested_reviewers = detect_reviewers(project_root)
        current_names = {r.name for r in reviewers}
        suggested_names = {r.name for r in suggested_reviewers}
        missing_names = suggested_names - current_names

        if missing_names:
            sorted_missing = sorted(missing_names)
            console.print("[yellow]Suggested reviewers not in current config:[/yellow]")
            for name in sorted_missing:
                reason = _get_detection_reason(name)
                console.print(f"  [yellow]![/yellow] {name} ({reason})")
            console.print()
            console.print("[dim]Run 'ralph review --force' to update configuration[/dim]")
            console.print()

    console.print(f"[dim]Loaded {len(reviewers)} reviewer(s)[/dim]")

    detected_languages = detect_languages(project_root)
    if detected_languages:
        lang_names = ", ".join(lang.value for lang in detected_languages)
        console.print(f"[dim]Detected languages: {lang_names}[/dim]")
    else:
        console.print("[dim]No specific languages detected[/dim]")

    if strict:
        console.print("[dim]Strict mode: warning-level reviewers are enforced[/dim]")

    console.print()

    review_service = ReviewLoopService(
        project_root=project_root,
        verbose=verbose,
    )

    results: list[ReviewerResult] = []
    total_reviewers = len(reviewers)

    for i, reviewer in enumerate(reviewers, start=1):
        if not review_service.should_run_reviewer(reviewer, detected_languages):
            logger.info(
                f"Skipping reviewer {reviewer.name} (language filter: {reviewer.languages})"
            )
            result = ReviewerResult(
                reviewer_name=reviewer.name,
                success=True,
                skipped=True,
                attempts=0,
            )
            results.append(result)
            review_service._append_review_summary(progress_path, reviewer, result)
            continue

        print_review_step(i, total_reviewers, reviewer.name)
        console.print()

        enforced = review_service.is_enforced(reviewer, strict)
        result = review_service.run_reviewer(reviewer, enforced=enforced)
        results.append(result)

        review_service._append_review_summary(progress_path, reviewer, result)

        if result.success:
            logger.info(f"Reviewer {reviewer.name} completed successfully")
        elif result.skipped:
            logger.info(f"Reviewer {reviewer.name} skipped")
        else:
            logger.warning(f"Reviewer {reviewer.name} failed after {result.attempts} attempts")

        console.print()

    console.print()
    console.print("[bold]Review Summary[/bold]")
    console.print()

    passed = 0
    failed = 0
    skipped = 0

    for result in results:
        if result.skipped:
            skipped += 1
            console.print(f"  [dim]- {result.reviewer_name}: skipped (language filter)[/dim]")
        elif result.success:
            passed += 1
            console.print(f"  [green][OK][/green] {result.reviewer_name}: passed")
        else:
            failed += 1
            error_info = f" ({result.error})" if result.error else ""
            attempts_text = f"failed after {result.attempts} attempt(s)"
            console.print(
                f"  [red][FAIL][/red] {result.reviewer_name}: {attempts_text}{error_info}"
            )

    console.print()
    console.print(f"[dim]Passed: {passed}, Failed: {failed}, Skipped: {skipped}[/dim]")

    if failed == 0:
        print_success("All reviews passed!")
        raise typer.Exit(0)
    else:
        print_error("Some reviews failed")
        raise typer.Exit(1)
