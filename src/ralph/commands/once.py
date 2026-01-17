"""Ralph once command - execute a single iteration."""

import typer

from ralph.utils import print_warning


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
    # These options are used in the full implementation
    _ = verbose
    _ = max_fix_attempts
    print_warning("Command not yet implemented")
    raise typer.Exit(1)
