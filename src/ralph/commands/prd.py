"""Ralph prd command - interactive PRD creation with Claude.

This module implements the 'ralph prd' command which launches
an interactive session with Claude to create a PRD.
"""

import logging
import os
from pathlib import Path

import typer

from ralph.services import ClaudeError, ClaudeService
from ralph.utils import console, print_error, print_success, print_warning

logger = logging.getLogger(__name__)


def _get_file_mtime(path: Path) -> float | None:
    """Get the modification time of a file, or None if it doesn't exist.

    Args:
        path: Path to the file.

    Returns:
        The mtime as a float, or None if the file doesn't exist.
    """
    if path.exists():
        return os.path.getmtime(path)
    return None


def _check_file_modified(
    output_path: Path,
    output: Path,
    mtime_before: float | None,
) -> None:
    """Check if the output file was created or modified and display appropriate message.

    Args:
        output_path: Full path to the output file.
        output: Relative output path for display.
        mtime_before: The mtime of the file before Claude ran, or None if it didn't exist.
    """
    mtime_after = _get_file_mtime(output_path)

    # File was created or modified
    if mtime_after is not None and (mtime_before is None or mtime_after > mtime_before):
        print_success(f"PRD saved to {output}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Review the PRD in [cyan]plans/SPEC.md[/cyan]")
        console.print("  2. Generate tasks: [cyan]ralph tasks plans/SPEC.md[/cyan]")
    else:
        # File was not created or not modified
        print_warning(f"PRD file was not modified at {output}")
        console.print("[dim]The session may have been cancelled or no changes were made.[/dim]")


def prd(
    output: Path = typer.Option(
        Path("plans/SPEC.md"),
        "--output",
        "-o",
        help="Output path for the PRD (default: plans/SPEC.md)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output"),
    input_text: str | None = typer.Option(
        None,
        "--input",
        "-i",
        help="Feature description for non-interactive PRD generation",
    ),
    file: Path | None = typer.Option(
        None,
        "--file",
        "-f",
        help="File containing the feature description for non-interactive PRD generation",
    ),
) -> None:
    """Create a PRD interactively with Claude.

    Launches Claude Code in interactive mode to help create a
    Product Requirements Document saved to plans/SPEC.md.

    With --input or --file, runs in non-interactive mode using the provided
    feature description.

    Claude will guide you through:
    - Clarifying your feature requirements
    - Structuring the PRD with proper sections
    - Writing clear acceptance criteria
    """
    project_root = Path.cwd()
    output_path = project_root / output

    plans_dir = project_root / "plans"
    if not plans_dir.exists():
        print_warning("plans/ directory not found.")
        console.print("Run [cyan]ralph init[/cyan] first to initialize the project.")
        raise typer.Exit(1)

    # Check for mutual exclusivity of --input and --file
    if input_text is not None and file is not None:
        print_error("Cannot use both --input and --file at the same time.")
        console.print("[dim]Use --input to provide a feature description directly,[/dim]")
        console.print("[dim]or --file to read from a file, but not both.[/dim]")
        raise typer.Exit(1)

    if output_path.exists():
        console.print(f"[bold yellow]Note:[/bold yellow] {output} already exists.")
        console.print("Claude will help you update or expand it.\n")

    # Non-interactive mode when --file is provided
    if file is not None:
        file_path = project_root / file
        if not file_path.exists():
            print_error(f"File not found: {file}")
            raise typer.Exit(1)
        feature_description = file_path.read_text().strip()
        if not feature_description:
            print_error(f"File is empty: {file}")
            raise typer.Exit(1)
        _run_non_interactive(project_root, output_path, output, verbose, feature_description)
        return

    # Non-interactive mode when --input is provided
    if input_text is not None:
        _run_non_interactive(project_root, output_path, output, verbose, input_text)
        return

    # Interactive mode (default)
    console.print("[bold]Interactive PRD Creation[/bold]")
    console.print()
    console.print("Claude will guide you through creating a Product Requirements Document (PRD).")
    console.print()
    console.print("[dim]Tips for a good PRD session:[/dim]")
    console.print("  • Describe the feature you want to build")
    console.print("  • Answer Claude's clarifying questions")
    console.print("  • Review and refine the generated PRD")
    console.print()
    console.print(f"[dim]Output will be saved to:[/dim] [cyan]{output}[/cyan]")
    console.print()
    console.print("[bold]Starting Claude Code...[/bold]")
    console.print()

    prompt = _build_prd_prompt(output_path)

    # Record mtime before Claude runs
    mtime_before = _get_file_mtime(output_path)

    try:
        claude = ClaudeService(working_dir=project_root, verbose=verbose)
        exit_code = claude.run_interactive(prompt)

        if exit_code == 0:
            console.print()
            _check_file_modified(output_path, output, mtime_before)
        else:
            print_warning("Claude Code exited with non-zero status.")
            raise typer.Exit(exit_code)

    except ClaudeError as e:
        print_error(f"Failed to launch Claude Code: {e}")
        raise typer.Exit(1) from e


def _run_non_interactive(
    project_root: Path,
    output_path: Path,
    output: Path,
    verbose: bool,
    feature_description: str,
) -> None:
    """Run PRD generation in non-interactive mode.

    Args:
        project_root: Path to the project root directory.
        output_path: Full path where the PRD should be saved.
        output: Relative output path for display.
        verbose: Whether to show verbose output.
        feature_description: The feature description to generate PRD for.

    Raises:
        typer.Exit: On error or non-zero exit code from Claude.
    """
    console.print("[bold]Non-Interactive PRD Generation[/bold]")
    console.print()
    console.print(f"[dim]Generating PRD for:[/dim] {feature_description}")
    console.print(f"[dim]Output will be saved to:[/dim] [cyan]{output}[/cyan]")
    console.print()
    console.print("[bold]Running Claude Code...[/bold]")
    console.print()

    prompt = _build_non_interactive_prd_prompt(output_path, feature_description)

    # Record mtime before Claude runs
    mtime_before = _get_file_mtime(output_path)

    try:
        claude = ClaudeService(working_dir=project_root, verbose=verbose)
        _, exit_code = claude.run_print_mode(prompt)

        if exit_code == 0:
            console.print()
            _check_file_modified(output_path, output, mtime_before)
        else:
            print_warning("Claude Code exited with non-zero status.")
            raise typer.Exit(exit_code)

    except ClaudeError as e:
        print_error(f"Failed to run Claude Code: {e}")
        raise typer.Exit(1) from e


def _build_non_interactive_prd_prompt(output_path: Path, feature_description: str) -> str:
    """Build the prompt for non-interactive PRD generation.

    Args:
        output_path: Path where the PRD should be saved.
        feature_description: The feature description provided by the user.

    Returns:
        The prompt string for Claude.
    """
    return f"""Create a Product Requirements Document (PRD) for the following feature:

{feature_description}

Structure the PRD with these sections:
- Overview: What problem does this solve?
- Goals: What are we trying to achieve?
- Non-Goals: What is explicitly out of scope?
- Requirements: Detailed functional requirements
- Technical Considerations: Implementation notes
- Success Criteria: How we know it's working

Based on the feature description provided, make reasonable assumptions where needed.
Write the PRD in clear, professional language.

Save the PRD to: {output_path}"""


def _build_prd_prompt(output_path: Path) -> str:
    """Build the prompt for interactive PRD creation.

    Args:
        output_path: Path where the PRD should be saved.

    Returns:
        The prompt string for Claude.
    """
    return f"""Help me create a Product Requirements Document (PRD) for a new feature.

Please guide me through the following:
1. Ask clarifying questions to understand the feature requirements
2. Help me define the scope and boundaries
3. Structure the PRD with these sections:
   - Overview: What problem does this solve?
   - Goals: What are we trying to achieve?
   - Non-Goals: What is explicitly out of scope?
   - Requirements: Detailed functional requirements
   - Technical Considerations: Implementation notes
   - Success Criteria: How we know it's working

Save the final PRD to: {output_path}

Start by asking me what feature I want to build."""
