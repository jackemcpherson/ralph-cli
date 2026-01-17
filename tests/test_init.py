"""Basic tests for ralph package."""

import re

from ralph import __version__


def test_version_is_defined() -> None:
    """Test version is defined and follows semver."""
    assert __version__
    assert re.match(r"^\d+\.\d+\.\d+", __version__)
