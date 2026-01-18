"""Ralph tasks command - convert spec to TASKS.json.

This module implements the 'ralph tasks' command which converts
a specification file into a structured TASKS.json file using Claude.
"""

import json
import logging
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import typer
from pydantic import ValidationError

from ralph.models import TasksFile, save_tasks
from ralph.services import ClaudeError, ClaudeService
from ralph.utils import console, print_error, print_success, read_file, write_file

logger = logging.getLogger(__name__)


def tasks(
    spec_file: Path = typer.Argument(
        ...,
        help="Path to the specification file (e.g., plans/SPEC.md)",
        exists=True,
        readable=True,
    ),
    output: Path = typer.Option(
        Path("plans/TASKS.json"),
        "--output",
        "-o",
        help="Output path for the tasks file (default: plans/TASKS.json)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output"),
    branch_name: str | None = typer.Option(
        None,
        "--branch",
        "-b",
        help="Git branch name for the feature (default: ralph/<project-name>)",
    ),
) -> None:
    """Convert a specification file to TASKS.json.

    Reads the provided spec file and uses Claude to break it down
    into user stories, outputting plans/TASKS.json.

    The generated TASKS.json follows the Ralph workflow format with:
    - User stories with acceptance criteria
    - Priority ordering
    - Pass/fail tracking for iterations
    """
    project_root = Path.cwd()
    output_path = project_root / output

    try:
        spec_content = read_file(spec_file)
    except FileNotFoundError:
        print_error(f"Spec file not found: {spec_file}")
        raise typer.Exit(1)
    except PermissionError:
        print_error(f"Permission denied reading: {spec_file}")
        raise typer.Exit(1)

    if not spec_content.strip():
        print_error("Spec file is empty. Please add content to your PRD first.")
        raise typer.Exit(1)

    if output_path.exists():
        console.print(f"[bold yellow]Note:[/bold yellow] {output} already exists.")
        console.print("It will be overwritten with new tasks.\n")

    console.print("[bold]Converting Spec to Tasks[/bold]")
    console.print()
    console.print(f"[dim]Reading spec from:[/dim] [cyan]{spec_file}[/cyan]")
    console.print(f"[dim]Output will be saved to:[/dim] [cyan]{output}[/cyan]")
    console.print()

    prompt = _build_tasks_prompt(spec_content, branch_name)

    console.print("[bold]Running Claude to generate tasks...[/bold]")
    console.print()

    try:
        claude = ClaudeService(working_dir=project_root, verbose=verbose)
        output_text, exit_code = claude.run_print_mode(prompt, stream=True)

        if exit_code != 0:
            print_error(f"Claude exited with code {exit_code}")
            if verbose:
                console.print("[dim]Claude output:[/dim]")
                console.print(output_text)
            raise typer.Exit(exit_code)

        json_content = _extract_json(output_text)

        if not json_content:
            print_error("Could not extract valid JSON from Claude's output.")
            console.print()
            console.print("[dim]Claude's output:[/dim]")
            console.print(output_text[:2000])
            raise typer.Exit(1)

        try:
            tasks_model = TasksFile.model_validate_json(json_content)
        except ValidationError as e:
            print_error("Claude's output does not match the expected TASKS.json format.")
            console.print()
            console.print("[dim]Validation errors:[/dim]")
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                console.print(f"  • {loc}: {error['msg']}")
            raise typer.Exit(1) from e

        save_tasks(tasks_model, output_path)

        # Archive PROGRESS.txt if it exists and has content
        archived_path = _archive_progress_file(project_root)
        if archived_path:
            console.print()
            console.print(
                f"[dim]Archived previous progress to[/dim] [cyan]{archived_path.name}[/cyan]"
            )

        story_count = len(tasks_model.user_stories)
        console.print()
        print_success(f"Generated {story_count} user stories in {output}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Review the tasks in [cyan]plans/TASKS.json[/cyan]")
        console.print("  2. Adjust priorities and acceptance criteria as needed")
        console.print("  3. Start iterations: [cyan]ralph once[/cyan] or [cyan]ralph loop[/cyan]")

    except ClaudeError as e:
        print_error(f"Failed to run Claude: {e}")
        raise typer.Exit(1) from e


def _build_tasks_prompt(spec_content: str, branch_name: str | None = None) -> str:
    """Build the prompt for task generation.

    Args:
        spec_content: Content of the specification file.
        branch_name: Optional git branch name for the feature.

    Returns:
        The prompt string for Claude.
    """
    branch_instruction = ""
    if branch_name:
        branch_instruction = f'\nUse this branch name: "{branch_name}"'
    else:
        branch_instruction = (
            '\nDerive the branch name from the project name (e.g., "ralph/<project-slug>")'
        )

    return f"""Convert the following Product Requirements Document (PRD) into a TASKS.json file.

IMPORTANT: Output ONLY valid JSON with no additional text, markdown, or explanation.

The JSON must follow this exact schema:
{{
  "project": "<ProjectName>",
  "branchName": "<ralph/feature-name>",
  "description": "<brief feature description>",
  "userStories": [
    {{
      "id": "<US-001>",
      "title": "<short title>",
      "description": "<As a [user], I want [feature] so that [benefit]>",
      "acceptanceCriteria": ["<criterion 1>", "<criterion 2>"],
      "priority": <1-N, lower is higher priority>,
      "passes": false,
      "notes": ""
    }}
  ]
}}

Guidelines for creating user stories:
1. Break down the spec into atomic, implementable stories
2. Each story should be completable in one iteration
3. Order by dependency (foundational work first, then features that build on it)
4. Include "Typecheck passes" in acceptance criteria for code changes
5. Write clear, testable acceptance criteria
6. Keep stories focused - if too large, split into multiple stories
7. Include setup/infrastructure stories before feature stories
8. Include test stories for critical functionality
{branch_instruction}

---

SPECIFICATION:

{spec_content}

---

Output the TASKS.json content now (JSON only, no markdown code blocks):"""


def _extract_json(text: str) -> str | None:
    """Extract JSON content from Claude's output.

    Handles various formats:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON with surrounding text

    Args:
        text: Claude's raw output text.

    Returns:
        Extracted JSON string, or None if no valid JSON found.
    """
    text = text.strip()

    if _is_valid_json(text):
        return text

    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, text)
    for match in matches:
        if _is_valid_json(match.strip()):
            return match.strip()

    json_pattern = r"\{[\s\S]*\}"
    matches = re.findall(json_pattern, text)
    for match in matches:
        if _is_valid_json(match):
            return match

    return None


def _is_valid_json(text: str) -> bool:
    """Check if text is valid JSON.

    Args:
        text: String to check.

    Returns:
        True if valid JSON, False otherwise.
    """
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


# Template for fresh PROGRESS.txt file (matches scaffold.py)
PROGRESS_TEMPLATE = """# Ralph Progress Log

## Codebase Patterns

(Add reusable patterns discovered during iterations here)

---

## Log

(Iteration entries will be appended below)

---
"""


def _archive_progress_file(project_root: Path) -> Path | None:
    """Archive existing PROGRESS.txt if it exists and has content.

    Archives the file to plans/PROGRESS.{timestamp}.txt and creates
    a fresh PROGRESS.txt with the header template.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Path to the archived file, or None if no archive was created.
    """
    progress_path = project_root / "plans" / "PROGRESS.txt"

    # Check if file exists
    if not progress_path.exists():
        return None

    # Check if file has content (non-empty)
    content = progress_path.read_text()
    if not content.strip():
        return None

    # Generate timestamp in YYYYMMDD_HHMMSS format
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    archive_path = project_root / "plans" / f"PROGRESS.{timestamp}.txt"

    # Archive the file
    shutil.copy2(progress_path, archive_path)

    # Create fresh PROGRESS.txt with header template
    write_file(progress_path, PROGRESS_TEMPLATE)

    return archive_path
