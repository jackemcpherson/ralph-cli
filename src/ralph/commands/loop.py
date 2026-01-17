"""Ralph loop command - run multiple iterations automatically."""

import typer

from ralph.utils import print_warning


def loop(
    iterations: int = typer.Argument(10, help="Number of iterations to run"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full JSON output"),
    max_fix_attempts: int = typer.Option(
        3, "--max-fix-attempts", help="Maximum attempts to fix failing checks"
    ),
) -> None:
    """Run multiple Ralph iterations automatically.

    Executes up to N iterations sequentially, stopping when all
    stories are complete or on persistent failure.
    """
    # These options are used in the full implementation
    _ = iterations
    _ = verbose
    _ = max_fix_attempts
    print_warning("Command not yet implemented")
    raise typer.Exit(1)
