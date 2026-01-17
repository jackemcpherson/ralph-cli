"""Ralph init command - scaffold a project for Ralph workflow."""

import typer

from ralph.utils import print_warning


def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
) -> None:
    """Scaffold a project for Ralph workflow.

    Creates plans/ directory with SPEC.md, TASKS.json, and PROGRESS.txt.
    Also creates CLAUDE.md and AGENTS.md with project-specific defaults.
    """
    print_warning("Command not yet implemented")
    raise typer.Exit(1)
