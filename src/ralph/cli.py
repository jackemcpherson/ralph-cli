"""Ralph CLI entry point."""

import typer

app = typer.Typer(
    name="ralph",
    help="Ralph CLI - Autonomous iteration pattern for Claude Code",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Ralph CLI - Autonomous iteration pattern for Claude Code."""
    pass


if __name__ == "__main__":
    app()
