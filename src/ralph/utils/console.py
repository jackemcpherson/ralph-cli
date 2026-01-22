"""Rich console utilities for consistent terminal output.

This module provides a shared Rich Console instance and helper functions
for displaying formatted terminal output with consistent styling.
"""

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console

logger = logging.getLogger(__name__)

# Legacy Windows encodings that require special handling
LEGACY_WINDOWS_ENCODINGS = frozenset({"cp1252", "cp437", "ascii"})


def create_console() -> Console:
    """Create a Rich Console with appropriate settings for the current terminal.

    On Windows terminals with legacy encodings (cp1252, cp437, ascii), enables
    legacy_windows mode to avoid unicode encoding errors. On UTF-8 terminals
    and non-Windows platforms, uses default Console settings.

    Returns:
        Console: A configured Rich Console instance.
    """
    # Only apply legacy mode on Windows with non-UTF-8 encodings
    if sys.platform == "win32":
        # Get stdout encoding, defaulting to utf-8 if not available
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        encoding = encoding.lower().replace("-", "")  # Normalize: UTF-8 -> utf8

        if encoding in LEGACY_WINDOWS_ENCODINGS:
            logger.debug(
                "Detected legacy Windows encoding '%s', enabling legacy_windows mode",
                encoding,
            )
            return Console(legacy_windows=True)

    return Console()


console = create_console()


def print_success(message: str) -> None:
    """Print a success message with a green checkmark.

    Args:
        message: The success message to display.
    """
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str) -> None:
    """Print an error message with a red X.

    Args:
        message: The error message to display.
    """
    console.print(f"[bold red]✗[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message with a yellow warning sign.

    Args:
        message: The warning message to display.
    """
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_step(step: int, total: int, message: str) -> None:
    """Print an iteration progress step.

    Args:
        step: Current step number (1-indexed).
        total: Total number of steps.
        message: Description of the current step.
    """
    console.print(f"[bold blue][{step}/{total}][/bold blue] {message}")


def print_review_step(step: int, total: int, reviewer_name: str) -> None:
    """Print a review progress step.

    Displays the review counter and reviewer name in a format consistent
    with the iteration loop, using 'Review X/Y' prefix.

    Args:
        step: Current review number (1-indexed).
        total: Total number of reviews.
        reviewer_name: Name of the reviewer being executed.
    """
    console.print(f"[bold blue][Review {step}/{total}][/bold blue] {reviewer_name}")


def print_fix_step(step: int, total: int, finding_id: str) -> None:
    """Print a fix progress step.

    Displays the fix counter and finding ID in a format consistent
    with the review loop, using 'Fix X/Y' prefix.

    Args:
        step: Current fix attempt number (1-indexed).
        total: Total number of findings to fix.
        finding_id: ID of the finding being fixed.
    """
    console.print(f"[bold blue][Fix {step}/{total}][/bold blue] {finding_id}")


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
