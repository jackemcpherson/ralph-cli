"""Ralph tasks command - convert spec to TASKS.json.

This module implements the 'ralph tasks' command which converts
a specification file into a structured TASKS.json file using Claude.
"""

import json
import logging
import re
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import typer
from pydantic import ValidationError

from ralph.models import TasksFile, save_tasks
from ralph.services import ClaudeError, ClaudeService, SkillNotFoundError
from ralph.services.scaffold import PROGRESS_TEMPLATE
from ralph.utils import (
    build_skill_prompt,
    console,
    print_error,
    print_success,
    read_file,
    write_file,
)

logger = logging.getLogger(__name__)

# Directories to exclude from file tree scanning
_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
    }
)

# Key files to include content from (read in order, stop at budget)
_KEY_FILES = [
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
]

# Maximum characters for the entire codebase summary section
_MAX_SUMMARY_CHARS = 12_000

# Maximum depth for file tree listing
_MAX_TREE_DEPTH = 4


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

    try:
        prompt = _build_prompt_from_skill(spec_content, branch_name)
    except SkillNotFoundError as e:
        print_error(f"Skill not found: {e}")
        raise typer.Exit(1) from e

    console.print("[bold]Running Claude to generate tasks...[/bold]")
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
            print_error(f"Claude exited with code {exit_code}")
            if verbose:
                console.print("[dim]Claude output:[/dim]")
                console.print(output_text)
            raise typer.Exit(exit_code)

        # Try to get valid JSON - first check if Claude wrote the file directly,
        # then fall back to extracting from stdout
        tasks_model = _get_tasks_from_output_or_file(output_text, output_path)

        if tasks_model is None:
            print_error("Could not extract valid JSON from Claude's output or file.")
            console.print()
            console.print("[dim]Claude's output:[/dim]")
            console.print(output_text[:2000])
            raise typer.Exit(1)

        save_tasks(tasks_model, output_path)

        _log_already_implemented(tasks_model)

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


def _iter_file_tree(root: Path, max_depth: int = _MAX_TREE_DEPTH) -> Iterator[str]:
    """Yield indented file tree lines for a directory.

    Walks the directory tree breadth-first, excluding common non-source
    directories. Each line is indented to show nesting depth.

    Args:
        root: The root directory to scan.
        max_depth: Maximum directory depth to descend into.

    Yields:
        Indented file/directory path lines.
    """

    def _should_exclude(name: str) -> bool:
        if name in _EXCLUDED_DIRS:
            return True
        return any(name.endswith(suffix) for suffix in (".egg-info",))

    def _walk(directory: Path, depth: int) -> Iterator[str]:
        if depth > max_depth:
            yield "  " * depth + "..."
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if _should_exclude(entry.name):
                continue
            if entry.is_dir():
                yield "  " * depth + entry.name + "/"
                yield from _walk(entry, depth + 1)
            else:
                yield "  " * depth + entry.name

    yield from _walk(root, 0)


def _gather_codebase_summary(project_root: Path) -> str:
    """Gather a heuristic codebase snapshot using filesystem scanning.

    Produces a summary containing:
    - A file tree (truncated at depth limit)
    - Contents of key project files (pyproject.toml, CLAUDE.md, etc.)

    The summary is budget-capped to avoid oversized prompts.

    Args:
        project_root: Path to the project root directory.

    Returns:
        A formatted string containing the codebase summary.
    """
    sections: list[str] = []

    # 1. File tree
    tree_lines = list(_iter_file_tree(project_root))
    tree_text = "\n".join(tree_lines)
    sections.append("### File Tree\n\n```\n" + tree_text + "\n```")

    # 2. Key file contents
    key_file_sections: list[str] = []
    remaining_budget = _MAX_SUMMARY_CHARS - len("\n\n".join(sections))

    for filename in _KEY_FILES:
        filepath = project_root / filename
        if not filepath.is_file():
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Truncate individual file content if needed
        if len(content) > 3000:
            content = content[:3000] + "\n... (truncated)"
        entry = f"### {filename}\n\n```\n{content}\n```"
        if len(entry) > remaining_budget:
            break
        key_file_sections.append(entry)
        remaining_budget -= len(entry) + 2  # account for join separator

    if key_file_sections:
        sections.extend(key_file_sections)

    return "\n\n".join(sections)


def _build_prompt_from_skill(spec_content: str, branch_name: str | None = None) -> str:
    """Build the prompt by loading the ralph/tasks skill and adding context.

    Args:
        spec_content: Content of the specification file.
        branch_name: Optional git branch name for the feature.

    Returns:
        The prompt string for Claude.

    Raises:
        SkillNotFoundError: If the ralph/tasks skill is not found.
    """
    project_root = Path.cwd()
    codebase_summary = _gather_codebase_summary(project_root)

    context_lines = [
        "---",
        "",
        "## Context for This Session",
        "",
    ]

    if branch_name:
        context_lines.append(f"**Branch name:** `{branch_name}`")
    else:
        context_lines.append(
            '**Branch name:** Derive from the project name (e.g., "ralph/<project-slug>")'
        )

    context_lines.extend(
        [
            "",
            "## Existing Codebase Summary",
            "",
            codebase_summary,
            "",
            "## Instructions for Already-Implemented Detection",
            "",
            "Review the codebase summary above alongside the specification. "
            "If a requirement from the spec appears to already be implemented "
            "in the existing codebase, mark that story with `passes: true` and "
            "add a note explaining why it appears already implemented "
            '(e.g., `"notes": "Already implemented: <evidence>"`). '
            "Only mark stories as already implemented when there is clear evidence "
            "in the file tree or key file contents.",
            "",
            "**Specification content:**",
            "",
            spec_content,
            "",
            "Generate the TASKS.json content now (JSON only, no markdown code blocks).",
        ]
    )

    context = "\n".join(context_lines)
    return build_skill_prompt("ralph/tasks", context)


def _log_already_implemented(tasks_model: TasksFile) -> None:
    """Log a summary of stories detected as already implemented.

    Counts stories where ``passes`` is ``True`` and displays each one
    with its ID and title so the developer understands what was
    auto-marked as complete.

    Args:
        tasks_model: The parsed TasksFile from Claude's output.
    """
    already_implemented = [s for s in tasks_model.user_stories if s.passes]
    if not already_implemented:
        return

    console.print()
    console.print(
        f"[bold yellow]\\[Tasks][/bold yellow] "
        f"{len(already_implemented)} stories detected as already implemented"
    )
    for story in already_implemented:
        console.print(f"  [dim]{story.id}:[/dim] {story.title}")


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


def _get_tasks_from_output_or_file(output_text: str, output_path: Path) -> TasksFile | None:
    """Get TasksFile from Claude's output or from the file if Claude wrote it directly.

    First tries to extract JSON from stdout (preferred since the skill instructs
    Claude to output JSON). Falls back to checking if Claude wrote the file directly.

    Args:
        output_text: Claude's stdout output.
        output_path: Path where TASKS.json should be written.

    Returns:
        TasksFile model if valid JSON found, None otherwise.
    """
    # First, try extracting from stdout (preferred - skill instructs Claude to output JSON)
    json_content = _extract_json(output_text)
    if json_content:
        try:
            return TasksFile.model_validate_json(json_content)
        except ValidationError as e:
            logger.warning(f"JSON from stdout didn't validate: {e}")

    # Fall back to checking if Claude wrote the file directly
    if output_path.exists():
        try:
            file_content = read_file(output_path)
            tasks_model = TasksFile.model_validate_json(file_content)
            logger.info("Loaded TASKS.json from file written by Claude")
            return tasks_model
        except (ValidationError, json.JSONDecodeError, OSError) as e:
            logger.debug(f"File exists but couldn't parse: {e}")

    return None


def _has_meaningful_content(content: str) -> bool:
    """Check if PROGRESS.txt content contains real iteration data.

    Detects whether the file contains actual iteration content beyond
    just the template boilerplate. Used to avoid archiving template-only files.

    Args:
        content: The content of the PROGRESS.txt file.

    Returns:
        True if meaningful iteration content is present, False otherwise.
    """
    # Iteration markers that indicate real progress entries
    iteration_markers = [
        "## Iteration",  # Iteration section header
        "### Story:",  # Story section header
        "**Status:**",  # Status marker in entries
        "**Completed:**",  # Completed marker in entries
        "### What was implemented",  # Implementation details section
        "### Tests written",  # Tests section
        "### Files changed",  # Files changed section
        "### Learnings",  # Learnings section
    ]

    # Check for any iteration marker in the content
    return any(marker in content for marker in iteration_markers)


def _archive_progress_file(project_root: Path) -> Path | None:
    """Archive existing PROGRESS.txt if it exists and has meaningful content.

    Archives the file to plans/PROGRESS.{timestamp}.txt and creates
    a fresh PROGRESS.txt with the header template. Skips archiving if the file
    only contains template boilerplate without any actual iteration content.

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

    # Check if file has meaningful iteration content beyond template
    if not _has_meaningful_content(content):
        return None

    # Generate timestamp in YYYYMMDD_HHMMSS format
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    archive_path = project_root / "plans" / f"PROGRESS.{timestamp}.txt"

    # Archive the file
    shutil.copy2(progress_path, archive_path)

    # Create fresh PROGRESS.txt with header template
    write_file(progress_path, PROGRESS_TEMPLATE)

    return archive_path
