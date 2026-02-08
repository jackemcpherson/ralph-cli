"""Ralph loop command - run multiple iterations automatically.

This module implements the 'ralph loop' command which runs multiple
Ralph iterations sequentially until all stories complete or failure.
"""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import typer
from pydantic import ValidationError

from ralph.commands.once import (
    _build_prompt_from_skill,
    _find_next_story,
)
from ralph.models import TasksFile, UserStory, load_reviewer_configs, load_tasks
from ralph.services import (
    ClaudeError,
    ClaudeService,
    GitError,
    GitService,
    ReviewerResult,
    ReviewLoopService,
    SkillNotFoundError,
    detect_languages,
)
from ralph.utils import (
    append_file,
    console,
    file_exists,
    print_error,
    print_review_step,
    print_step,
    print_success,
    print_warning,
)

logger = logging.getLogger(__name__)


class IterationOutcome(StrEnum):
    """Outcome of a single story iteration.

    Attributes:
        PASSED: Story completed successfully.
        FAILED: Story did not pass checks.
        ALL_COMPLETE: All stories are now complete (COMPLETE tag detected).
        SKILL_ERROR: Could not load the required skill.
        CLAUDE_ERROR: Error running Claude.
    """

    PASSED = "passed"
    FAILED = "failed"
    ALL_COMPLETE = "all_complete"
    SKILL_ERROR = "skill_error"
    CLAUDE_ERROR = "claude_error"


class LoopStopReason(StrEnum):
    """Reasons for stopping the loop.

    Contains constants representing the various conditions that
    can cause the iteration loop to terminate.

    Attributes:
        ALL_COMPLETE: All user stories passed successfully.
        MAX_ITERATIONS: Reached the maximum iteration count.
        PERSISTENT_FAILURE: Same story failed multiple times consecutively.
        TRANSIENT_FAILURE: A transient error occurred during iteration.
        NO_TASKS: No tasks were found to process.
        BRANCH_MISMATCH: Could not switch to the expected branch.
    """

    ALL_COMPLETE = "all_complete"
    MAX_ITERATIONS = "max_iterations"
    PERSISTENT_FAILURE = "persistent_failure"
    TRANSIENT_FAILURE = "transient_failure"
    NO_TASKS = "no_tasks"
    BRANCH_MISMATCH = "branch_mismatch"


def _execute_story(
    *,
    project_root: Path,
    tasks_path: Path,
    story: UserStory,
    max_fix_attempts: int,
    verbose: bool,
) -> IterationOutcome:
    """Execute a single story iteration with Claude.

    Builds the prompt, runs Claude, and checks whether the story passed.

    Args:
        project_root: Path to the project root directory.
        tasks_path: Path to TASKS.json for status verification.
        story: The UserStory to implement.
        max_fix_attempts: Maximum attempts to fix failing checks.
        verbose: Whether to show verbose output.

    Returns:
        IterationOutcome indicating what happened during execution.
    """
    try:
        prompt = _build_prompt_from_skill(story, max_fix_attempts)
    except SkillNotFoundError as e:
        print_error(f"Skill not found: {e}")
        return IterationOutcome.SKILL_ERROR

    try:
        claude = ClaudeService(working_dir=project_root, verbose=verbose)
        output_text, _ = claude.run_print_mode(
            prompt,
            stream=True,
            skip_permissions=True,
            append_system_prompt=ClaudeService.AUTONOMOUS_MODE_PROMPT,
        )
    except ClaudeError as e:
        print_error(f"Claude error: {e}")
        return IterationOutcome.CLAUDE_ERROR

    console.print()

    if "<ralph>COMPLETE</ralph>" in output_text:
        return IterationOutcome.ALL_COMPLETE

    story_passed = _check_story_status(tasks_path, story.id)

    if story_passed:
        print_success(f"Story {story.id} completed!")
        return IterationOutcome.PASSED

    print_warning(f"Story {story.id} did not pass")
    return IterationOutcome.FAILED


def _check_story_status(tasks_path: Path, story_id: str) -> bool:
    """Check if a story has passed by reloading TASKS.json.

    Args:
        tasks_path: Path to TASKS.json.
        story_id: ID of the story to check.

    Returns:
        True if the story passes, False otherwise.
    """
    try:
        updated_tasks = load_tasks(tasks_path)
        updated_story = next((s for s in updated_tasks.user_stories if s.id == story_id), None)
        return updated_story is not None and updated_story.passes
    except (FileNotFoundError, ValidationError, OSError) as e:
        logger.warning(f"Could not verify story status: {e}")
        return False


def _display_loop_summary(
    *,
    stop_reason: LoopStopReason,
    completed_in_loop: int,
    total_stories: int,
    completed_before: int,
    tasks_path: Path,
    iterations: int,
) -> tuple[int, int]:
    """Display the loop summary statistics.

    Args:
        stop_reason: Reason the loop stopped.
        completed_in_loop: Number of stories completed in this run.
        total_stories: Total number of stories.
        completed_before: Stories completed before this run.
        tasks_path: Path to TASKS.json for final status check.
        iterations: Maximum iteration count.

    Returns:
        Tuple of (final_completed, final_remaining) counts.
    """
    console.print("[bold]Loop Summary[/bold]")
    console.print()

    try:
        final_tasks = load_tasks(tasks_path)
        final_completed = sum(1 for s in final_tasks.user_stories if s.passes)
        final_remaining = total_stories - final_completed
    except (FileNotFoundError, ValidationError, OSError) as e:
        logger.warning(f"Could not load final task status: {e}")
        final_completed = completed_before + completed_in_loop
        final_remaining = total_stories - final_completed

    console.print(f"[dim]Stories completed this run:[/dim] {completed_in_loop}")
    console.print(f"[dim]Total completed:[/dim] {final_completed}/{total_stories}")
    console.print(f"[dim]Remaining:[/dim] {final_remaining}")
    console.print()

    if stop_reason == LoopStopReason.MAX_ITERATIONS:
        console.print(f"[dim]Reached maximum of {iterations} iterations.[/dim]")
    elif stop_reason == LoopStopReason.PERSISTENT_FAILURE:
        print_error("Stopped due to persistent failure on the same story.")
        console.print("[dim]Manual intervention may be required.[/dim]")
    elif stop_reason == LoopStopReason.TRANSIENT_FAILURE:
        print_error("Stopped due to transient failure.")

    return final_completed, final_remaining


def _reload_tasks(tasks_path: Path) -> TasksFile | None:
    """Reload TASKS.json from disk.

    Args:
        tasks_path: Path to TASKS.json.

    Returns:
        TasksFile if loaded successfully, None on error.
    """
    try:
        return load_tasks(tasks_path)
    except (FileNotFoundError, ValidationError, OSError) as e:
        logger.error(f"Failed to reload TASKS.json: {e}")
        print_error("Failed to reload TASKS.json")
        return None


def _check_consecutive_failures(
    current_story_id: str,
    failed_story_id: str | None,
    consecutive_failures: int,
) -> tuple[LoopStopReason, bool]:
    """Check if we should stop due to consecutive failures on the same story.

    Args:
        current_story_id: ID of the story about to be executed.
        failed_story_id: ID of the last story that failed, or None.
        consecutive_failures: Number of consecutive failures on the same story.

    Returns:
        Tuple of (stop_reason, should_break). If should_break is True,
        the loop should terminate with the given stop_reason.
    """
    if failed_story_id == current_story_id:
        consecutive_failures += 1
        if consecutive_failures >= 2:
            print_error(
                f"Story {current_story_id} failed {consecutive_failures} times. Stopping loop."
            )
            return LoopStopReason.PERSISTENT_FAILURE, True

    return LoopStopReason.MAX_ITERATIONS, False


def loop(
    iterations: int = typer.Argument(10, help="Number of iterations to run"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full JSON output"),
    max_fix_attempts: int = typer.Option(
        3, "--max-fix-attempts", help="Maximum attempts to fix failing checks"
    ),
    skip_review: bool = typer.Option(
        False,
        "--skip-review",
        help="Skip the automated review loop after all stories complete",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warning-level reviewers as blocking during the review loop",
    ),
    no_fix: bool = typer.Option(
        False,
        "--no-fix",
        help="Report review findings without applying automated fixes",
    ),
) -> None:
    """Run multiple Ralph iterations automatically.

    Executes up to N iterations sequentially, stopping when all
    stories are complete or on persistent failure.

    After all stories pass, an automated review loop runs configured
    reviewers unless --skip-review is provided. Use --strict to enforce
    warning-level reviewers as blocking.
    """
    project_root = Path.cwd()
    tasks_path = project_root / "plans" / "TASKS.json"
    progress_path = project_root / "plans" / "PROGRESS.txt"

    if not file_exists(tasks_path):
        print_error("No plans/TASKS.json found. Run 'ralph init' or 'ralph tasks' first.")
        raise typer.Exit(1)

    try:
        tasks = load_tasks(tasks_path)
    except FileNotFoundError:
        print_error("Could not load plans/TASKS.json")
        raise typer.Exit(1)
    except (ValidationError, OSError) as e:
        print_error(f"Error parsing TASKS.json: {e}")
        raise typer.Exit(1)

    git = GitService(working_dir=project_root)
    branch_ready = _setup_branch(git, tasks.branch_name, project_root)

    if not branch_ready:
        print_error("Could not set up the feature branch. Aborting loop.")
        raise typer.Exit(1)

    console.print("[bold]Ralph Loop[/bold]")
    console.print()
    console.print(f"[dim]Project:[/dim] {tasks.project}")
    console.print(f"[dim]Branch:[/dim] {tasks.branch_name}")
    console.print(f"[dim]Max iterations:[/dim] {iterations}")
    console.print()

    total_stories = len(tasks.user_stories)
    completed_before = sum(1 for s in tasks.user_stories if s.passes)
    remaining = total_stories - completed_before

    console.print(f"[dim]Total stories:[/dim] {total_stories}")
    console.print(f"[dim]Already complete:[/dim] {completed_before}")
    console.print(f"[dim]Remaining:[/dim] {remaining}")
    console.print()
    console.print(
        "[dim]Running Claude with auto-approved permissions for autonomous iteration[/dim]"
    )
    console.print()

    if remaining == 0:
        print_success("All stories already complete!")
        raise typer.Exit(0)

    completed_in_loop = 0
    failed_story_id: str | None = None
    consecutive_failures = 0
    stop_reason: LoopStopReason = LoopStopReason.MAX_ITERATIONS

    for i in range(iterations):
        iteration_num = i + 1

        tasks = _reload_tasks(tasks_path)
        if tasks is None:
            stop_reason = LoopStopReason.TRANSIENT_FAILURE
            break

        next_story = _find_next_story(tasks)
        if next_story is None:
            stop_reason = LoopStopReason.ALL_COMPLETE
            break

        stop_reason, should_break = _check_consecutive_failures(
            next_story.id, failed_story_id, consecutive_failures
        )
        if should_break:
            break

        if failed_story_id != next_story.id:
            failed_story_id = None
            consecutive_failures = 0

        print_step(iteration_num, iterations, f"[cyan]{next_story.id}[/cyan]: {next_story.title}")
        console.print()

        outcome = _execute_story(
            project_root=project_root,
            tasks_path=tasks_path,
            story=next_story,
            max_fix_attempts=max_fix_attempts,
            verbose=verbose,
        )

        if outcome == IterationOutcome.ALL_COMPLETE:
            completed_in_loop += 1
            stop_reason = LoopStopReason.ALL_COMPLETE
            break

        if outcome in (IterationOutcome.SKILL_ERROR, IterationOutcome.CLAUDE_ERROR):
            stop_reason = LoopStopReason.TRANSIENT_FAILURE
            break

        if outcome == IterationOutcome.PASSED:
            completed_in_loop += 1
            failed_story_id = None
            consecutive_failures = 0
            _append_loop_progress(progress_path, iteration_num, next_story.id, next_story.title)
        else:
            failed_story_id = next_story.id
            consecutive_failures = 1

        console.print()

    _display_loop_summary(
        stop_reason=stop_reason,
        completed_in_loop=completed_in_loop,
        total_stories=total_stories,
        completed_before=completed_before,
        tasks_path=tasks_path,
        iterations=iterations,
    )

    if stop_reason == LoopStopReason.ALL_COMPLETE:
        print_success("All stories complete!")

        # Run review loop unless skipped
        if skip_review:
            console.print("[dim]Skipping review loop (--skip-review flag)[/dim]")
        else:
            review_success = _run_review_loop(
                project_root=project_root,
                progress_path=progress_path,
                strict=strict,
                verbose=verbose,
                no_fix=no_fix,
            )
            if not review_success:
                print_warning("Review loop completed with failures")
                # Still exit 0 since all stories passed - reviews are informational
    elif stop_reason == LoopStopReason.MAX_ITERATIONS:
        console.print(f"[dim]Reached maximum of {iterations} iterations.[/dim]")
    elif stop_reason == LoopStopReason.PERSISTENT_FAILURE:
        print_error("Stopped due to persistent failure on the same story.")
        console.print("[dim]Manual intervention may be required.[/dim]")
    elif stop_reason == LoopStopReason.TRANSIENT_FAILURE:
        print_error("Stopped due to transient failure.")

    if stop_reason == LoopStopReason.ALL_COMPLETE:
        raise typer.Exit(0)
    elif stop_reason == LoopStopReason.MAX_ITERATIONS and completed_in_loop > 0:
        raise typer.Exit(0)
    else:
        raise typer.Exit(1)


def _setup_branch(git: GitService, branch_name: str, project_root: Path) -> bool:
    """Set up the feature branch for the loop.

    Checks if we're on the correct branch, and if not, handles the switch.

    Args:
        git: GitService instance.
        branch_name: Expected branch name from TASKS.json.
        project_root: Path to project root.

    Returns:
        True if branch is ready, False if setup failed.
    """
    try:
        current_branch = git.get_current_branch()
    except GitError as e:
        print_error(f"Could not get current branch: {e}")
        return False

    if current_branch == branch_name:
        console.print(f"[dim]On correct branch: {branch_name}[/dim]")
        return True

    # Check for uncommitted changes before switching
    try:
        has_changes = git.has_changes()
    except GitError:
        has_changes = False

    if has_changes:
        print_warning(f"Uncommitted changes on branch '{current_branch}'.")
        console.print("[dim]Please commit or stash your changes before switching branches.[/dim]")

        console.print()
        console.print(f"[dim]Expected branch: {branch_name}[/dim]")
        console.print(f"[dim]Current branch: {current_branch}[/dim]")

        print_warning("Continuing may lose uncommitted work.")

    try:
        created = git.checkout_or_create_branch(branch_name)
        if created:
            console.print(f"[dim]Created new branch: {branch_name}[/dim]")
        else:
            console.print(f"[dim]Switched to branch: {branch_name}[/dim]")
        return True
    except GitError as e:
        print_error(f"Could not switch to branch '{branch_name}': {e}")
        return False


def _append_loop_progress(
    progress_path: Path, iteration_num: int, story_id: str, story_title: str
) -> None:
    """Append a brief loop progress note to PROGRESS.txt.

    Args:
        progress_path: Path to PROGRESS.txt.
        iteration_num: Current iteration number.
        story_id: ID of the completed story.
        story_title: Title of the completed story.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    note = (
        f"\n[Ralph Loop] {timestamp} - Iteration {iteration_num}: "
        f"{story_id} ({story_title}) completed\n"
    )

    try:
        append_file(progress_path, note)
    except OSError as e:
        logger.warning(f"Could not append to progress file: {e}")


def _run_review_loop(
    *,
    project_root: Path,
    progress_path: Path,
    strict: bool,
    verbose: bool,
    no_fix: bool = False,
) -> bool:
    """Run the automated review loop after all stories complete.

    Loads configured reviewers from CLAUDE.md, detects project languages,
    and executes each reviewer in order with progress display.

    Args:
        project_root: Path to the project root directory.
        progress_path: Path to PROGRESS.txt for logging.
        strict: Whether to treat warning-level reviewers as blocking.
        verbose: Whether to show verbose output.
        no_fix: Whether to skip automated fixes for review findings.

    Returns:
        True if all enforced reviewers passed, False otherwise.
    """
    console.print()
    console.print("[bold]Review Loop[/bold]")
    console.print()

    # Load reviewer configuration from CLAUDE.md
    claude_md_path = project_root / "CLAUDE.md"
    reviewers = load_reviewer_configs(claude_md_path)

    console.print(f"[dim]Loaded {len(reviewers)} reviewer(s) from configuration[/dim]")

    # Detect project languages
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

    # Run each reviewer with progress display
    results = []
    total_reviewers = len(reviewers)

    for i, reviewer in enumerate(reviewers, start=1):
        # Check if reviewer should be skipped due to language filter
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

    return failed == 0
