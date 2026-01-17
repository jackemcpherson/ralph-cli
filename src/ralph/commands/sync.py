"""Ralph sync command - sync skills to ~/.claude/skills/."""

import typer

from ralph.utils import print_warning


def sync() -> None:
    """Sync Ralph skills to Claude Code.

    Copies skill definitions from the repo's skills/ directory
    to ~/.claude/skills/ for global access.
    """
    print_warning("Command not yet implemented")
    raise typer.Exit(1)
