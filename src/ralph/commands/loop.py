"""Ralph loop command - run multiple iterations automatically."""

from datetime import UTC, datetime
from pathlib import Path

import typer

# Reuse the iteration prompt from once.py
from ralph.commands.once import ITERATION_PROMPT
from ralph.models import TasksFile, UserStory, load_tasks
from ralph.services import ClaudeError, ClaudeService, GitError, GitService
from ralph.utils import (
    append_file,
    console,
    file_exists,
    print_error,
    print_step,
    print_success,
    print_warning,
)


class LoopStopReason:
    """Reasons for stopping the loop."""

    ALL_COMPLETE = "all_complete"
    MAX_ITERATIONS = "max_iterations"
    PERSISTENT_FAILURE = "persistent_failure"
    TRANSIENT_FAILURE = "transient_failure"
    NO_TASKS = "no_tasks"
    BRANCH_MISMATCH = "branch_mismatch"


def loop(
    iterations: int = typer.Argument(10, help="Number of iterations to run"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full JSON output"),
    max_fix_attempts: int = typer.Option(
        3, "--max-fix-attempts", help="Maximum attempts to fix failing checks"
    ),
) -> None:
    """Run multiple Ralph iterations automatically.

    Executes up to N iterations sequentially, stopping when all
    stories are complete or on persistent failure.
    """
    project_root = Path.cwd()
    tasks_path = project_root / "plans" / "TASKS.json"
    progress_path = project_root / "plans" / "PROGRESS.txt"

    # Check for TASKS.json
    if not file_exists(tasks_path):
        print_error("No plans/TASKS.json found. Run 'ralph init' or 'ralph tasks' first.")
        raise typer.Exit(1)

    # Load tasks
    try:
        tasks = load_tasks(tasks_path)
    except FileNotFoundError:
        print_error("Could not load plans/TASKS.json")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Error parsing TASKS.json: {e}")
        raise typer.Exit(1)

    # Check/create feature branch
    git = GitService(working_dir=project_root)
    branch_ready = _setup_branch(git, tasks.branch_name, project_root)

    if not branch_ready:
        print_error("Could not set up the feature branch. Aborting loop.")
        raise typer.Exit(1)

    # Display loop info
    console.print("[bold]Ralph Loop[/bold]")
    console.print()
    console.print(f"[dim]Project:[/dim] {tasks.project}")
    console.print(f"[dim]Branch:[/dim] {tasks.branch_name}")
    console.print(f"[dim]Max iterations:[/dim] {iterations}")
    console.print()

    # Count initial stats
    total_stories = len(tasks.user_stories)
    completed_before = sum(1 for s in tasks.user_stories if s.passes)
    remaining = total_stories - completed_before

    console.print(f"[dim]Total stories:[/dim] {total_stories}")
    console.print(f"[dim]Already complete:[/dim] {completed_before}")
    console.print(f"[dim]Remaining:[/dim] {remaining}")
    console.print()

    if remaining == 0:
        print_success("All stories already complete!")
        raise typer.Exit(0)

    # Track loop progress
    completed_in_loop = 0
    failed_story_id: str | None = None
    consecutive_failures = 0
    stop_reason: str = LoopStopReason.MAX_ITERATIONS

    # Run iterations
    for i in range(iterations):
        iteration_num = i + 1

        # Reload tasks to get current state
        try:
            tasks = load_tasks(tasks_path)
        except Exception:
            stop_reason = LoopStopReason.TRANSIENT_FAILURE
            print_error("Failed to reload TASKS.json")
            break

        # Find next story
        next_story = _find_next_story(tasks)

        if next_story is None:
            stop_reason = LoopStopReason.ALL_COMPLETE
            break

        # Check for persistent failure on same story
        if failed_story_id == next_story.id:
            consecutive_failures += 1
            if consecutive_failures >= 2:
                stop_reason = LoopStopReason.PERSISTENT_FAILURE
                print_error(
                    f"Story {next_story.id} failed {consecutive_failures} times. Stopping loop."
                )
                break
        else:
            failed_story_id = None
            consecutive_failures = 0

        # Display iteration info
        print_step(iteration_num, iterations, f"[cyan]{next_story.id}[/cyan]: {next_story.title}")
        console.print()

        # Build iteration prompt
        prompt = _build_iteration_prompt(next_story, max_fix_attempts)

        # Run Claude
        try:
            claude = ClaudeService(working_dir=project_root, verbose=verbose)
            output_text, exit_code = claude.run_print_mode(prompt, stream=True)
        except ClaudeError as e:
            print_error(f"Claude error: {e}")
            stop_reason = LoopStopReason.TRANSIENT_FAILURE
            break

        console.print()

        # Check for completion signal
        if "<ralph>COMPLETE</ralph>" in output_text:
            completed_in_loop += 1
            stop_reason = LoopStopReason.ALL_COMPLETE
            break

        # Check if story passed by reloading tasks
        story_passed = False
        try:
            updated_tasks = load_tasks(tasks_path)
            updated_story = next(
                (s for s in updated_tasks.user_stories if s.id == next_story.id), None
            )
            story_passed = updated_story is not None and updated_story.passes
        except Exception:
            # If we can't reload, assume failure
            story_passed = False

        if story_passed:
            completed_in_loop += 1
            print_success(f"Story {next_story.id} completed!")
            failed_story_id = None
            consecutive_failures = 0

            # Append loop progress note
            _append_loop_progress(progress_path, iteration_num, next_story.id, next_story.title)
        else:
            print_warning(f"Story {next_story.id} did not pass")
            failed_story_id = next_story.id
            consecutive_failures = 1

        console.print()

    # Final summary
    console.print("[bold]Loop Summary[/bold]")
    console.print()

    # Reload final state
    try:
        final_tasks = load_tasks(tasks_path)
        final_completed = sum(1 for s in final_tasks.user_stories if s.passes)
        final_remaining = total_stories - final_completed
    except Exception:
        final_completed = completed_before + completed_in_loop
        final_remaining = total_stories - final_completed

    console.print(f"[dim]Stories completed this run:[/dim] {completed_in_loop}")
    console.print(f"[dim]Total completed:[/dim] {final_completed}/{total_stories}")
    console.print(f"[dim]Remaining:[/dim] {final_remaining}")
    console.print()

    # Display stop reason
    if stop_reason == LoopStopReason.ALL_COMPLETE:
        print_success("All stories complete!")
    elif stop_reason == LoopStopReason.MAX_ITERATIONS:
        console.print(f"[dim]Reached maximum of {iterations} iterations.[/dim]")
    elif stop_reason == LoopStopReason.PERSISTENT_FAILURE:
        print_error("Stopped due to persistent failure on the same story.")
        console.print("[dim]Manual intervention may be required.[/dim]")
    elif stop_reason == LoopStopReason.TRANSIENT_FAILURE:
        print_error("Stopped due to transient failure.")

    # Exit with appropriate code
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

        # Archive note: We're not automatically archiving/stashing because
        # that could lead to confusion. The user should explicitly handle this.
        console.print()
        console.print(f"[dim]Expected branch: {branch_name}[/dim]")
        console.print(f"[dim]Current branch: {current_branch}[/dim]")

        # We'll still try to switch, but warn the user
        print_warning("Continuing may lose uncommitted work.")

    # Try to checkout or create the branch
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


def _find_next_story(tasks: TasksFile) -> UserStory | None:
    """Find the highest-priority story with passes=false.

    Args:
        tasks: TasksFile model.

    Returns:
        The next UserStory to work on, or None if all complete.
    """
    incomplete = [s for s in tasks.user_stories if not s.passes]
    if not incomplete:
        return None

    # Sort by priority (lower = higher priority)
    incomplete.sort(key=lambda s: s.priority)
    return incomplete[0]


def _build_iteration_prompt(story: UserStory, max_fix_attempts: int) -> str:
    """Build the iteration prompt for Claude.

    Args:
        story: UserStory to implement.
        max_fix_attempts: Maximum fix attempts.

    Returns:
        The formatted prompt string.
    """
    # Format acceptance criteria
    criteria_lines = "\n".join(f"  - {c}" for c in story.acceptance_criteria)

    return ITERATION_PROMPT.format(
        max_fix_attempts=max_fix_attempts,
        story_id=story.id,
        story_title=story.title,
        story_description=story.description,
        acceptance_criteria=criteria_lines,
    )


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
    except Exception:
        # Don't fail if we can't append
        pass
