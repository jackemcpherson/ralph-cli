"""Tests for conftest utility functions."""

from tests.conftest import normalize_paths


class TestNormalizePaths:
    """Tests for the normalize_paths function."""

    def test_converts_single_backslash(self) -> None:
        """Single backslash is converted to forward slash."""
        assert normalize_paths("plans\\TASKS.json") == "plans/TASKS.json"

    def test_converts_multiple_backslashes(self) -> None:
        """Multiple backslashes are all converted."""
        assert normalize_paths("a\\b\\c\\d") == "a/b/c/d"

    def test_handles_windows_absolute_path(self) -> None:
        """Windows absolute paths are normalized correctly."""
        assert normalize_paths("C:\\Users\\test\\file.py") == "C:/Users/test/file.py"

    def test_preserves_forward_slashes(self) -> None:
        """Forward slashes remain unchanged."""
        assert normalize_paths("plans/TASKS.json") == "plans/TASKS.json"

    def test_handles_mixed_separators(self) -> None:
        """Mixed forward and backslashes are normalized."""
        assert normalize_paths("a/b\\c/d\\e") == "a/b/c/d/e"

    def test_handles_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalize_paths("") == ""

    def test_handles_no_path_separators(self) -> None:
        """String without separators is unchanged."""
        assert normalize_paths("filename.txt") == "filename.txt"

    def test_handles_double_backslashes(self) -> None:
        """Double backslashes are each converted."""
        assert normalize_paths("path\\\\file") == "path//file"

    def test_handles_trailing_backslash(self) -> None:
        """Trailing backslash is converted."""
        assert normalize_paths("path\\to\\dir\\") == "path/to/dir/"


class TestPathNormalizerFixture:
    """Tests for the path_normalizer fixture."""

    def test_fixture_returns_normalize_paths_function(self, path_normalizer) -> None:
        """Fixture returns the normalize_paths function."""
        assert path_normalizer is normalize_paths

    def test_fixture_can_be_used_for_normalization(self, path_normalizer) -> None:
        """Fixture can be used to normalize paths."""
        result = path_normalizer("plans\\TASKS.json")
        assert result == "plans/TASKS.json"

    def test_fixture_works_with_complex_paths(self, path_normalizer) -> None:
        """Fixture handles complex Windows paths."""
        result = path_normalizer("C:\\Program Files\\App\\config\\settings.json")
        assert result == "C:/Program Files/App/config/settings.json"
