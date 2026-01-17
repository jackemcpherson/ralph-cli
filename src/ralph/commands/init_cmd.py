"""Ralph init command - scaffold a project for Ralph workflow."""

from pathlib import Path

import typer

from ralph.services import ClaudeService, ProjectType, ScaffoldService
from ralph.utils import console, print_success, print_warning


def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    skip_claude: bool = typer.Option(
        False, "--skip-claude", help="Skip invoking Claude Code /init"
    ),
    project_name: str | None = typer.Option(
        None, "--name", "-n", help="Project name (defaults to directory name)"
    ),
) -> None:
    """Scaffold a project for Ralph workflow.

    Creates plans/ directory with SPEC.md, TASKS.json, and PROGRESS.txt.
    Also creates CLAUDE.md and AGENTS.md with project-specific defaults.
    """
    project_root = Path.cwd()

    # Check if Ralph files already exist
    existing_files = _check_existing_files(project_root)
    if existing_files and not force:
        print_warning("Ralph workflow files already exist:")
        for file in existing_files:
            console.print(f"  - {file}")
        console.print()
        console.print("Use [bold]--force[/bold] to overwrite existing files.")
        raise typer.Exit(1)

    # Create scaffold service and detect project type
    scaffold = ScaffoldService(project_root=project_root)
    project_type = scaffold.detect_project_type()

    # Show project type detection result
    if project_type != ProjectType.UNKNOWN:
        console.print(f"Detected project type: [bold cyan]{project_type.value}[/bold cyan]")
    else:
        print_warning("Could not detect project type. Using generic template.")

    # Create all Ralph workflow files
    console.print()
    console.print("[bold]Creating Ralph workflow files...[/bold]")

    created_files = scaffold.scaffold_all(project_name=project_name)

    for file_type, path in created_files.items():
        if file_type != "plans_dir":
            relative_path = path.relative_to(project_root)
            print_success(f"Created {relative_path}")

    # Optionally invoke Claude Code /init to enhance files
    if not skip_claude:
        console.print()
        console.print("[bold]Invoking Claude Code /init to enhance project files...[/bold]")
        console.print(
            "[dim]This will analyze your project and update CLAUDE.md and AGENTS.md.[/dim]"
        )
        console.print()

        try:
            claude = ClaudeService(working_dir=project_root)
            exit_code = claude.run_interactive("/init")
            if exit_code != 0:
                print_warning("Claude Code /init completed with non-zero exit code.")
        except Exception as e:
            print_warning(f"Failed to run Claude Code /init: {e}")
            console.print("[dim]You can run 'claude /init' manually later.[/dim]")

    # Display success message and next steps
    console.print()
    print_success("[bold]Ralph workflow initialized![/bold]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Edit [cyan]plans/SPEC.md[/cyan] with your feature specification")
    console.print("     Or run [cyan]ralph prd[/cyan] to create one interactively")
    console.print()
    console.print("  2. Generate tasks from your spec:")
    console.print("     [cyan]ralph tasks plans/SPEC.md[/cyan]")
    console.print()
    console.print("  3. Start the autonomous iteration loop:")
    console.print("     [cyan]ralph loop[/cyan]")
    console.print()
    console.print("[dim]Tip: Review CLAUDE.md to customize quality checks for your project.[/dim]")


def _check_existing_files(project_root: Path) -> list[str]:
    """Check for existing Ralph workflow files.

    Args:
        project_root: The project root directory.

    Returns:
        List of relative paths to existing files.
    """
    files_to_check = [
        "plans/SPEC.md",
        "plans/TASKS.json",
        "plans/PROGRESS.txt",
        "CLAUDE.md",
        "AGENTS.md",
    ]

    existing = []
    for file_path in files_to_check:
        if (project_root / file_path).exists():
            existing.append(file_path)

    return existing
