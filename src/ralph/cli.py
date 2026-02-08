"""Ralph CLI entry point.

This module provides the main entry point for the Ralph CLI application,
a tool for autonomous iteration patterns with Claude Code.
"""

import logging

import typer

from ralph import __version__
from ralph.commands import init, loop, once, prd, review, sync, tasks

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="ralph",
    help="Ralph CLI - Autonomous iteration pattern for Claude Code",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Handle the version flag callback.

    Args:
        value: Whether the version flag was provided.

    Raises:
        typer.Exit: Always raised after printing version when value is True.
    """
    if value:
        typer.echo(f"ralph {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Ralph CLI - Autonomous iteration pattern for Claude Code."""


app.command(name="init", help="Scaffold a project for Ralph workflow")(init)
app.command(name="prd", help="Create a PRD interactively with Claude")(prd)
app.command(name="tasks", help="Convert a specification file to TASKS.json")(tasks)
app.command(name="once", help="Execute a single Ralph iteration")(once)
app.command(name="loop", help="Run multiple Ralph iterations automatically")(loop)
app.command(name="sync", help="Sync Ralph skills to Claude Code")(sync)
app.command(name="review", help="Run the review loop with automatic configuration")(review)


if __name__ == "__main__":
    app()
