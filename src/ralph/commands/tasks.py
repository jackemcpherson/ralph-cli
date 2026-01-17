"""Ralph tasks command - convert spec to TASKS.json."""

from pathlib import Path

import typer

from ralph.utils import print_warning


def tasks(
    spec_file: Path = typer.Argument(
        ...,
        help="Path to the specification file (e.g., plans/SPEC.md)",
        exists=True,
        readable=True,
    ),
) -> None:
    """Convert a specification file to TASKS.json.

    Reads the provided spec file and uses Claude to break it down
    into user stories, outputting plans/TASKS.json.
    """
    # spec_file is used in the full implementation
    _ = spec_file
    print_warning("Command not yet implemented")
    raise typer.Exit(1)
