"""Ralph review command - run the review loop with automatic configuration.

This module implements the 'ralph review' command which automatically
detects and configures reviewers on first run, then executes the review loop.
"""

import logging
from pathlib import Path

import typer

from ralph.models import load_reviewer_configs
from ralph.services import (
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


# Mapping of reviewer names to their detection reasons
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
) -> None:
    """Run the review loop with automatic configuration.

    On first run (no existing config): detects reviewers based on project
    contents, writes configuration to CLAUDE.md, then executes the review loop.

    On subsequent runs: uses existing configuration from CLAUDE.md.
    """
    project_root = Path.cwd()
    claude_md_path = project_root / "CLAUDE.md"
    progress_path = project_root / "plans" / "PROGRESS.txt"

    console.print("[bold]Ralph Review[/bold]")
    console.print()

    # Check if this is first run (no existing config)
    is_first_run = not has_reviewer_config(claude_md_path)

    if is_first_run:
        console.print("[dim]First run detected - configuring reviewers...[/dim]")
        console.print()

        # Detect reviewers based on project contents
        reviewers = detect_reviewers(project_root)

        # Display what was detected and why
        console.print("[bold]Detected Reviewers:[/bold]")
        for reviewer in reviewers:
            reason = _get_detection_reason(reviewer.name)
            console.print(f"  [green]+[/green] {reviewer.name} ({reason})")

        console.print()

        # Write configuration to CLAUDE.md
        write_reviewer_config(claude_md_path, reviewers)
        console.print(f"[dim]Configuration written to {claude_md_path}[/dim]")
        console.print()
    else:
        console.print("[dim]Using existing reviewer configuration[/dim]")
        console.print()

        # Load existing configuration
        reviewers = load_reviewer_configs(claude_md_path)

        # Check for suggested reviewers not in current config
        suggested_reviewers = detect_reviewers(project_root)
        current_names = {r.name for r in reviewers}
        suggested_names = {r.name for r in suggested_reviewers}
        missing_names = suggested_names - current_names

        if missing_names:
            # Sort for consistent output
            sorted_missing = sorted(missing_names)
            console.print("[yellow]Suggested reviewers not in current config:[/yellow]")
            for name in sorted_missing:
                reason = _get_detection_reason(name)
                console.print(f"  [yellow]![/yellow] {name} ({reason})")
            console.print()
            console.print("[dim]Run 'ralph review --force' to update configuration[/dim]")
            console.print()

    console.print(f"[dim]Loaded {len(reviewers)} reviewer(s)[/dim]")

    # Detect project languages for filtering
    detected_languages = detect_languages(project_root)
    if detected_languages:
        lang_names = ", ".join(lang.value for lang in detected_languages)
        console.print(f"[dim]Detected languages: {lang_names}[/dim]")
    else:
        console.print("[dim]No specific languages detected[/dim]")

    if strict:
        console.print("[dim]Strict mode: warning-level reviewers are enforced[/dim]")

    console.print()

    # Create review loop service and run
    review_service = ReviewLoopService(
        project_root=project_root,
        verbose=verbose,
    )

    # Run each reviewer with progress display
    results = []
    total_reviewers = len(reviewers)

    for i, reviewer in enumerate(reviewers, start=1):
        # Check if reviewer should be skipped due to language filter
        if not review_service.should_run_reviewer(reviewer, detected_languages):
            logger.info(
                f"Skipping reviewer {reviewer.name} (language filter: {reviewer.languages})"
            )
            from ralph.services import ReviewerResult

            result = ReviewerResult(
                reviewer_name=reviewer.name,
                success=True,
                skipped=True,
                attempts=0,
            )
            results.append(result)
            review_service._append_review_summary(progress_path, reviewer, result)
            continue

        # Display progress counter and reviewer name
        print_review_step(i, total_reviewers, reviewer.name)
        console.print()

        # Run the reviewer
        enforced = review_service.is_enforced(reviewer, strict)
        result = review_service.run_reviewer(reviewer, enforced=enforced)
        results.append(result)

        # Log to progress file
        review_service._append_review_summary(progress_path, reviewer, result)

        # Log result
        if result.success:
            logger.info(f"Reviewer {reviewer.name} completed successfully")
        elif result.skipped:
            logger.info(f"Reviewer {reviewer.name} skipped")
        else:
            logger.warning(f"Reviewer {reviewer.name} failed after {result.attempts} attempts")

        console.print()

    # Display summary
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
