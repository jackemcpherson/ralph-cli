"""Ralph prd command - interactive PRD creation with Claude."""

import typer

from ralph.utils import print_warning


def prd() -> None:
    """Create a PRD interactively with Claude.

    Launches Claude Code in interactive mode to help create a
    Product Requirements Document saved to plans/SPEC.md.
    """
    print_warning("Command not yet implemented")
    raise typer.Exit(1)
