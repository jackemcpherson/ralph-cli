"""Rich console utilities for consistent terminal output."""

from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console

# Shared console instance for consistent output across the application
console = Console()


def print_success(message: str) -> None:
    """Print a success message with a green checkmark."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str) -> None:
    """Print an error message with a red X."""
    console.print(f"[bold red]✗[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message with a yellow warning sign."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_step(step: int, total: int, message: str) -> None:
    """Print an iteration progress step.

    Args:
        step: Current step number (1-indexed).
        total: Total number of steps.
        message: Description of the current step.
    """
    console.print(f"[bold blue][{step}/{total}][/bold blue] {message}")


@contextmanager
def create_spinner(message: str) -> Iterator[None]:
    """Create a spinner context manager for long operations.

    Args:
        message: The status message to display while spinning.

    Yields:
        None: The spinner runs while the context is active.
    """
    with console.status(message, spinner="dots"):
        yield
