"""Shared pytest fixtures for Ralph CLI tests."""

import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def mock_shutil_which():
    """Automatically mock shutil.which to return a fake Claude CLI path.

    This ensures tests pass in CI environments where Claude CLI is not installed.
    """
    with patch("shutil.which", return_value="/usr/bin/claude"):
        yield


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for testing commands."""
    return CliRunner()
