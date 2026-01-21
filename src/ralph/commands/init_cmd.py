"""Ralph init command - scaffold a project for Ralph workflow.

This module implements the 'ralph init' command which creates
the plans directory structure and configuration files.
"""

import logging
import subprocess
from pathlib import Path

import typer
from rich.prompt import Confirm

from ralph.commands.prd import prd as prd_command
from ralph.services import ClaudeError, ClaudeService, ProjectType, ScaffoldService
from ralph.utils import console, print_success, print_warning

logger = logging.getLogger(__name__)


def _is_git_repo(project_root: Path) -> bool:
    """Check if the directory is inside a git repository.

    Args:
        project_root: The directory to check.

    Returns:
        True if inside a git repo, False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # git not installed
        return False


def _init_git_repo(project_root: Path) -> bool:
    """Initialize a new git repository.

    Args:
        project_root: The directory to initialize.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "init"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _create_initial_commit(project_root: Path) -> bool:
    """Create an initial git commit with the scaffolded files.

    Args:
        project_root: The project root directory.

    Returns:
        True if successful, False otherwise.
    """
    try:
        add_result = subprocess.run(
            ["git", "add", "."],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if add_result.returncode != 0:
            logger.warning(f"git add failed: {add_result.stderr}")
            return False

        commit_result = subprocess.run(
            ["git", "commit", "-m", "Initial commit: Ralph workflow setup"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        # Return code 1 with "nothing to commit" is not an error
        if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout:
            logger.warning(f"git commit failed: {commit_result.stderr}")
            return False

        return True
    except FileNotFoundError:
        return False


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

    existing_files = _check_existing_files(project_root)
    if existing_files and not force:
        print_warning("Ralph workflow files already exist:")
        for file in existing_files:
            console.print(f"  - {file}")
        console.print()
        console.print("Use [bold]--force[/bold] to overwrite existing files.")
        raise typer.Exit(1)

    initialized_git = False
    if not _is_git_repo(project_root):
        console.print("[bold]Initializing git repository...[/bold]")
        if _init_git_repo(project_root):
            print_success("Initialized git repository")
            initialized_git = True
        else:
            print_warning("Could not initialize git repository. Git may not be installed.")
        console.print()

    scaffold = ScaffoldService(project_root=project_root)
    project_type = scaffold.detect_project_type()

    if project_type != ProjectType.UNKNOWN:
        console.print(f"Detected project type: [bold cyan]{project_type.value}[/bold cyan]")
    else:
        print_warning("Could not detect project type. Using generic template.")

    # Check for existing PRD content BEFORE scaffolding (scaffolding may overwrite it)
    prd_path = project_root / "plans" / "SPEC.md"
    had_prd_content_before = _has_prd_content(prd_path)

    console.print()
    console.print("[bold]Creating Ralph workflow files...[/bold]")

    # Skip CHANGELOG.md creation if it already exists (it's persistent memory)
    changelog_existed = (project_root / "CHANGELOG.md").exists()
    created_files = scaffold.scaffold_all(
        project_name=project_name, skip_changelog=changelog_existed
    )

    for file_type, path in created_files.items():
        if file_type == "plans_dir":
            continue
        relative_path = path.relative_to(project_root)
        print_success(f"Created {relative_path}")

    if changelog_existed:
        console.print("[dim]  Skipped CHANGELOG.md (already exists)[/dim]")

    if not had_prd_content_before:
        _handle_missing_prd(prd_path, project_root)

    if not skip_claude:
        console.print()
        console.print("[bold]Invoking Claude Code /init to enhance project files...[/bold]")
        console.print(
            "[dim]This will analyze your project and update CLAUDE.md and AGENTS.md.[/dim]"
        )
        console.print()

        try:
            claude = ClaudeService(working_dir=project_root)
            exit_code = claude.run_interactive(
                "/init",
                skip_permissions=True,
                append_system_prompt=ClaudeService.AUTONOMOUS_MODE_PROMPT,
            )
            if exit_code != 0:
                print_warning("Claude Code /init completed with non-zero exit code.")
        except (OSError, ClaudeError) as e:
            print_warning(f"Failed to run Claude Code /init: {e}")
            console.print("[dim]You can run 'claude /init' manually later.[/dim]")

    if initialized_git:
        console.print()
        console.print("[bold]Creating initial commit...[/bold]")
        if _create_initial_commit(project_root):
            print_success("Created initial commit: 'Initial commit: Ralph workflow setup'")
        else:
            print_warning("Could not create initial commit. You may need to commit manually.")

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
        "CHANGELOG.md",
    ]

    return [f for f in files_to_check if (project_root / f).exists()]


def _has_prd_content(prd_path: Path) -> bool:
    """Check if the PRD file has meaningful content beyond the template.

    The scaffolded SPEC.md template contains placeholder brackets like
    `[Describe the feature...]` and `[Goal 1]`. This function checks if
    the user has replaced these placeholders with actual content.

    Args:
        prd_path: Path to the PRD file (plans/SPEC.md).

    Returns:
        True if the file has meaningful content, False otherwise.
    """
    if not prd_path.exists():
        return False

    content = prd_path.read_text().strip()

    # Empty file has no content
    if not content:
        return False

    # The scaffold template uses placeholder markers in brackets like:
    # [Describe the feature or project you want to build]
    # [Goal 1], [Goal 2], [Requirement 1], etc.
    # If the file still contains these, it hasn't been filled in
    placeholder_patterns = [
        "[Describe the feature",
        "[Goal 1]",
        "[Requirement 1]",
        "[What this feature will NOT do]",
        "[Describe the high-level architecture]",
    ]

    # Check if any scaffold placeholder patterns are still present
    has_placeholders = any(pattern in content for pattern in placeholder_patterns)

    # If it has placeholders, it's still template content
    if has_placeholders:
        return False

    # Also check for explicit template comment markers
    template_markers = [
        "<!-- Replace this",
        "[Your feature",
    ]

    if any(marker in content for marker in template_markers):
        return False

    # Check for actual content: must have at least one section heading followed
    # by actual text (not just another heading or placeholder)
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## "):  # Section heading
            # Check if there's actual content after this heading
            for remaining in lines[i + 1 :]:
                stripped = remaining.strip()
                # Skip empty lines and subheadings
                if not stripped or stripped.startswith("#"):
                    continue
                # Found actual content line
                # Make sure it's not just a placeholder bracket
                if stripped.startswith("[") and stripped.endswith("]"):
                    continue
                # Found real content
                return True
            break

    return False


def _handle_missing_prd(prd_path: Path, project_root: Path) -> None:
    """Handle the case when PRD is missing or empty.

    Prompts the user to create a PRD using the prd command, or continues
    without one if they decline.

    Args:
        prd_path: Path to the PRD file (plans/SPEC.md).
        project_root: Path to the project root directory.
    """
    console.print()
    print_warning("No PRD found at plans/SPEC.md")
    console.print()
    console.print(
        "[dim]A PRD (Product Requirements Document) helps Claude Code understand "
        "your project goals.[/dim]"
    )
    console.print()

    if Confirm.ask("Would you like to create a PRD first?", default=True):
        console.print()
        console.print("[bold]Launching PRD creation...[/bold]")
        console.print()
        try:
            # Invoke the prd command to create the specification
            # Use the default output path which is plans/SPEC.md
            # Pass all parameters explicitly to avoid Typer Option defaults not being applied
            prd_command(output=Path("plans/SPEC.md"), verbose=False, input_text=None, file=None)
        except typer.Exit:
            # PRD command completed (either successfully or user cancelled)
            pass
        except (OSError, ClaudeError) as e:
            print_warning(f"PRD creation failed: {e}")
            console.print("[dim]You can create a PRD later with 'ralph prd'.[/dim]")
    else:
        console.print()
        console.print(
            "[dim]Proceeding without PRD. You can create one later with "
            "'ralph prd' or edit plans/SPEC.md directly.[/dim]"
        )
