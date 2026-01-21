"""Ralph once command - execute a single iteration.

This module implements the 'ralph once' command which picks the
highest-priority incomplete story, implements it, and commits on success.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

import typer

from ralph.models import TasksFile, UserStory, load_tasks
from ralph.services import ClaudeError, ClaudeService, SkillNotFoundError
from ralph.utils import (
    append_file,
    build_skill_prompt,
    console,
    file_exists,
    print_error,
    print_success,
    print_warning,
)

logger = logging.getLogger(__name__)


def once(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full JSON output"),
    max_fix_attempts: int = typer.Option(
        3, "--max-fix-attempts", help="Maximum attempts to fix failing checks"
    ),
) -> None:
    """Execute a single Ralph iteration.

    Picks the highest-priority story with passes=false,
    implements it, runs quality checks, and commits on success.
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
    except Exception as e:
        print_error(f"Error parsing TASKS.json: {e}")
        raise typer.Exit(1)

    next_story = _find_next_story(tasks)

    if next_story is None:
        print_success("All stories complete!")
        console.print()
        console.print("[dim]No more stories to implement.[/dim]")
        raise typer.Exit(0)

    console.print("[bold]Ralph Iteration[/bold]")
    console.print()
    console.print(f"[dim]Project:[/dim] {tasks.project}")
    console.print(f"[dim]Branch:[/dim] {tasks.branch_name}")
    console.print()
    console.print("[bold]Story to implement:[/bold]")
    console.print(f"  [cyan]{next_story.id}[/cyan]: {next_story.title}")
    console.print(f"  [dim]{next_story.description}[/dim]")
    console.print()

    console.print("[bold]Acceptance Criteria:[/bold]")
    for criterion in next_story.acceptance_criteria:
        console.print(f"  • {criterion}")
    console.print()

    incomplete_count = sum(1 for s in tasks.user_stories if not s.passes)
    console.print(f"[dim]Stories remaining: {incomplete_count}[/dim]")
    console.print()

    # Load skill content and build prompt
    try:
        prompt = _build_prompt_from_skill(project_root, next_story, max_fix_attempts)
    except SkillNotFoundError as e:
        print_error(f"Skill not found: {e}")
        raise typer.Exit(1) from e

    console.print("[bold]Running Claude Code...[/bold]")
    console.print(
        "[dim]Running Claude with auto-approved permissions for autonomous iteration[/dim]"
    )
    console.print()

    try:
        claude = ClaudeService(working_dir=project_root, verbose=verbose)
        output_text, exit_code = claude.run_print_mode(
            prompt,
            stream=True,
            skip_permissions=True,
            append_system_prompt=ClaudeService.AUTONOMOUS_MODE_PROMPT,
        )

        if exit_code != 0:
            print_warning(f"Claude exited with code {exit_code}")

    except ClaudeError as e:
        print_error(f"Failed to run Claude: {e}")
        raise typer.Exit(1) from e

    console.print()

    all_complete = "<ralph>COMPLETE</ralph>" in output_text

    updated_tasks: TasksFile | None = None
    updated_story: UserStory | None = None
    story_passed = False

    try:
        updated_tasks = load_tasks(tasks_path)
        updated_story = next((s for s in updated_tasks.user_stories if s.id == next_story.id), None)
        story_passed = updated_story is not None and updated_story.passes
    except Exception:
        story_passed = exit_code == 0

    console.print("[bold]Iteration Summary[/bold]")
    console.print()

    if story_passed:
        print_success(f"Story {next_story.id} completed successfully!")
        if updated_story and updated_story.notes:
            console.print(f"[dim]Notes: {updated_story.notes}[/dim]")
    else:
        print_error(f"Story {next_story.id} did not pass")
        console.print("[dim]The story may require manual intervention.[/dim]")

    if all_complete:
        console.print()
        print_success("All stories are now complete!")
        console.print("[dim]Feature implementation finished.[/dim]")
    elif updated_tasks is not None:
        remaining = sum(1 for s in updated_tasks.user_stories if not s.passes)
        console.print()
        console.print(f"[dim]Stories remaining: {remaining}[/dim]")

    if story_passed:
        _append_cli_summary(progress_path, next_story.id, next_story.title, all_complete)
        raise typer.Exit(0)

    raise typer.Exit(1)


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

    incomplete.sort(key=lambda s: s.priority)
    return incomplete[0]


def _build_prompt_from_skill(project_root: Path, story: UserStory, max_fix_attempts: int) -> str:
    """Build the prompt by referencing the ralph-iteration skill and adding context.

    Args:
        project_root: Path to the project root directory.
        story: UserStory to implement.
        max_fix_attempts: Maximum fix attempts.

    Returns:
        The prompt string for Claude.

    Raises:
        SkillNotFoundError: If the ralph-iteration skill is not found.
    """
    # Build context section with story details
    criteria_lines = "\n".join(f"  - {c}" for c in story.acceptance_criteria)

    context_lines = [
        "---",
        "",
        "## Context for This Session",
        "",
        f"**Max fix attempts:** {max_fix_attempts}",
        "",
        "## Current Story",
        "",
        "You are implementing the following story:",
        "",
        f"**ID:** {story.id}",
        f"**Title:** {story.title}",
        f"**Description:** {story.description}",
        "",
        "**Acceptance Criteria:**",
        criteria_lines,
        "",
        "Begin implementation now. Read the codebase, implement the story, "
        "run quality checks, and commit your changes.",
    ]

    context = "\n".join(context_lines)
    return build_skill_prompt(project_root, "ralph-iteration", context)


def _append_cli_summary(
    progress_path: Path, story_id: str, story_title: str, all_complete: bool
) -> None:
    """Append a brief CLI summary to PROGRESS.txt.

    This is a minimal summary noting that ralph once completed successfully.
    Claude should have already appended detailed progress.

    Args:
        progress_path: Path to PROGRESS.txt.
        story_id: ID of the completed story.
        story_title: Title of the completed story.
        all_complete: Whether all stories are now complete.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    summary = f"\n[Ralph CLI] {timestamp} - {story_id} ({story_title}) completed successfully"
    if all_complete:
        summary += " - All stories complete!"
    summary += "\n"

    try:
        append_file(progress_path, summary)
    except Exception:
        pass
