"""Basic tests for ralph package."""

from ralph import __version__


def test_version() -> None:
    """Test version is defined."""
    assert __version__ == "0.1.0"
