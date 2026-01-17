"""Ralph once command - execute a single iteration.

This module implements the 'ralph once' command which picks the
highest-priority incomplete story, implements it, and commits on success.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

import typer

from ralph.models import TasksFile, UserStory, load_tasks
from ralph.services import ClaudeError, ClaudeService
from ralph.utils import append_file, console, file_exists, print_error, print_success, print_warning

logger = logging.getLogger(__name__)

ITERATION_PROMPT = """You are an autonomous coding agent working on a software project \
using the Ralph workflow.

## Your Task

1. Read the task list at `plans/TASKS.json`
2. Read the progress log at `plans/PROGRESS.txt` (check **Codebase Patterns** section first)
3. Read `CLAUDE.md` for project-specific quality checks and conventions
4. Check you're on the correct branch from `branchName` in TASKS.json. \
If not, check it out or create from main.
5. Pick the **highest priority** user story where `passes: false`
6. Implement that single user story
7. **Write tests** for the new functionality (see Testing Requirements below)
8. Run quality checks (defined in `CLAUDE.md` under `<!-- RALPH:CHECKS:START -->`)
9. If checks fail, fix the issues and re-run (up to {max_fix_attempts} attempts)
10. Update `CLAUDE.md` and `AGENTS.md` if you discover reusable patterns (see below)
11. If checks pass, commit ALL changes with message: `feat: [Story ID] - [Story Title]`
12. Update `plans/TASKS.json` to set `passes: true` for the completed story
13. Append your progress to `plans/PROGRESS.txt`

## Quality Checks

Quality checks are defined in `CLAUDE.md` in a structured YAML block:

```markdown
<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: npm run typecheck
    required: true
```
<!-- RALPH:CHECKS:END -->
```

Run each check in order. If a `required: true` check fails:
1. Analyze the error
2. Fix the issue
3. Re-run all checks
4. Repeat up to {max_fix_attempts} times total

Only proceed to commit if ALL required checks pass.

## Testing Requirements

Every story implementation must include appropriate tests. Follow these guidelines:

**What to test:**
- New functions and methods you create
- Edge cases and error handling
- Integration points with existing code
- Any behavior specified in acceptance criteria

**Test quality standards:**
- Tests should be meaningful, not just for coverage
- Test behavior, not implementation details
- Include both happy path and error cases
- Use descriptive test names that explain what's being tested

**Test location:**
- Follow the project's existing test structure
- Co-locate tests with code if that's the project convention
- Use the project's established testing framework

**When tests might be minimal:**
- Pure configuration changes
- Documentation-only updates
- Simple copy/text changes

If unsure about testing approach, check `plans/PROGRESS.txt` for patterns \
from previous iterations or existing tests in the codebase for conventions.

## Progress Report Format

APPEND to `plans/PROGRESS.txt` (never replace, always append):

```
## [Date/Time] - [Story ID]

**Story:** [Story Title]

### What was implemented
- [Bullet points of changes]

### Tests written
- [List of new tests added]
- [What behaviors they verify]

### Files changed
- [List of modified files]

### Learnings for future iterations
- [Patterns discovered]
- [Gotchas encountered]
- [Useful context]

---
```

The learnings section is critical—it helps future iterations avoid \
repeating mistakes and understand the codebase better.

## Consolidate Patterns

If you discover a **reusable pattern** that future iterations should know, \
add it to the `## Codebase Patterns` section at the TOP of `plans/PROGRESS.txt` \
(create it if it doesn't exist). This section consolidates the most important learnings:

```
## Codebase Patterns

- Example: Use `sql<number>` template for aggregations
- Example: Always use `IF NOT EXISTS` for migrations
- Example: Export types from actions.ts for UI components
```

Only add patterns that are **general and reusable**, not story-specific details.

## Update CLAUDE.md and AGENTS.md

Before committing, check if any edited files have learnings worth preserving. \
**Both files must be kept in sync.**

1. **Identify directories with edited files** - Look at which directories you modified
2. **Check for patterns worth preserving** - Did you discover something \
future developers/agents should know?
3. **Update both files** - Add the same learnings to both `CLAUDE.md` and `AGENTS.md`

**Examples of good additions:**
- "When modifying X, also update Y to keep them in sync"
- "This module uses pattern Z for all API calls"
- "Tests require the dev server running on PORT 3000"
- "Field names must match the template exactly"

**Do NOT add:**
- Story-specific implementation details
- Temporary debugging notes
- Information already in `plans/PROGRESS.txt`

## TASKS.json Format

The task file follows this structure:

```json
{{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Feature description",
  "userStories": [
    {{
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2",
        "Typecheck passes"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }}
  ]
}}
```

- Pick the story with the lowest `priority` number where `passes: false`
- After completion, set `passes: true`
- Add any relevant notes to the `notes` field

## Stop Condition

After completing a user story, check if ALL stories have `passes: true`.

If ALL stories are complete and passing, output exactly:

```
<ralph>COMPLETE</ralph>
```

If there are still stories with `passes: false`, end your response normally \
(another iteration will pick up the next story).

## Important Rules

- Work on **ONE story** per iteration
- **Write tests** for new functionality before considering a story complete
- Commit frequently (after each successful story)
- Keep all quality checks passing
- Read the Codebase Patterns section in `plans/PROGRESS.txt` before starting
- Always check `CLAUDE.md` for project-specific instructions
- Keep `CLAUDE.md` and `AGENTS.md` in sync when adding patterns

## Current Story

You are implementing the following story:

**ID:** {story_id}
**Title:** {story_title}
**Description:** {story_description}

**Acceptance Criteria:**
{acceptance_criteria}

Begin implementation now. Read the codebase, implement the story, \
run quality checks, and commit your changes."""


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

    prompt = _build_iteration_prompt(next_story, max_fix_attempts)

    console.print("[bold]Running Claude Code...[/bold]")
    console.print(
        "[dim]Running Claude with auto-approved permissions for autonomous iteration[/dim]"
    )
    console.print()

    try:
        claude = ClaudeService(working_dir=project_root, verbose=verbose)
        output_text, exit_code = claude.run_print_mode(prompt, stream=True, skip_permissions=True)

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

    if story_passed:
        raise typer.Exit(0)
    else:
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


def _build_iteration_prompt(story: UserStory, max_fix_attempts: int) -> str:
    """Build the iteration prompt for Claude.

    Args:
        story: UserStory to implement.
        max_fix_attempts: Maximum fix attempts.

    Returns:
        The formatted prompt string.
    """
    criteria_lines = "\n".join(f"  - {c}" for c in story.acceptance_criteria)

    return ITERATION_PROMPT.format(
        max_fix_attempts=max_fix_attempts,
        story_id=story.id,
        story_title=story.title,
        story_description=story.description,
        acceptance_criteria=criteria_lines,
    )


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
