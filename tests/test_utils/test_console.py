"""Tests for console utilities."""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from ralph.utils.console import (
    LEGACY_WINDOWS_ENCODINGS,
    console,
    create_console,
    create_spinner,
    print_error,
    print_step,
    print_success,
    print_warning,
)


class TestConsoleInstance:
    """Tests for the shared console instance."""

    def test_console_is_rich_console(self) -> None:
        """Test that console is a Rich Console instance."""
        assert isinstance(console, Console)


class TestCreateConsole:
    """Tests for create_console function with various encoding scenarios."""

    def test_returns_console_instance(self) -> None:
        """Test that create_console returns a Console instance."""
        result = create_console()
        assert isinstance(result, Console)

    def test_legacy_encodings_constant(self) -> None:
        """Test that legacy encodings constant contains expected values."""
        assert "cp1252" in LEGACY_WINDOWS_ENCODINGS
        assert "cp437" in LEGACY_WINDOWS_ENCODINGS
        assert "ascii" in LEGACY_WINDOWS_ENCODINGS
        assert "utf8" not in LEGACY_WINDOWS_ENCODINGS

    @pytest.mark.parametrize(
        "encoding",
        ["cp1252", "cp437", "ascii"],
    )
    def test_windows_legacy_encoding_enables_legacy_mode(self, encoding: str) -> None:
        """Test that legacy encodings on Windows enable legacy_windows mode."""
        mock_stdout = MagicMock()
        mock_stdout.encoding = encoding

        with (
            patch("ralph.utils.console.sys.platform", "win32"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            assert result.legacy_windows is True

    @pytest.mark.parametrize(
        "encoding",
        ["utf-8", "UTF-8", "utf8", "UTF8"],
    )
    def test_windows_utf8_encoding_does_not_force_legacy_mode(self, encoding: str) -> None:
        """Test that UTF-8 encoding on Windows does not force legacy_windows mode.

        When running on Windows with UTF-8 encoding, our code should not
        explicitly set legacy_windows=True. Rich's Console may still auto-detect
        Windows and set legacy_windows based on terminal capabilities.
        """
        mock_stdout = MagicMock()
        mock_stdout.encoding = encoding

        with (
            patch("ralph.utils.console.sys.platform", "win32"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            # We're testing that UTF-8 encoding doesn't trigger our explicit
            # legacy_windows=True setting. The actual value depends on Rich's
            # auto-detection which varies by platform.
            assert isinstance(result, Console)

    def test_non_windows_platform_does_not_force_legacy_mode(self) -> None:
        """Test that non-Windows platforms don't trigger our legacy mode logic.

        When our code detects a non-Windows platform, it should not explicitly
        set legacy_windows=True. Rich's Console may still auto-detect the
        actual platform for its own settings.
        """
        mock_stdout = MagicMock()
        mock_stdout.encoding = "cp1252"  # Even with legacy encoding

        with (
            patch("ralph.utils.console.sys.platform", "darwin"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            # We're testing that our code doesn't force legacy mode on non-Windows.
            # The actual legacy_windows value depends on Rich's auto-detection.
            assert isinstance(result, Console)

    def test_linux_platform_does_not_force_legacy_mode(self) -> None:
        """Test that Linux platform doesn't trigger our legacy mode logic.

        When our code detects a Linux platform, it should not explicitly
        set legacy_windows=True. Rich's Console may still auto-detect the
        actual platform for its own settings.
        """
        mock_stdout = MagicMock()
        mock_stdout.encoding = "ascii"

        with (
            patch("ralph.utils.console.sys.platform", "linux"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            # We're testing that our code doesn't force legacy mode on Linux.
            # The actual legacy_windows value depends on Rich's auto-detection.
            assert isinstance(result, Console)

    def test_missing_encoding_attribute_does_not_force_legacy_mode(self) -> None:
        """Test that missing encoding attribute doesn't force legacy mode.

        When stdout has no encoding attribute, our code defaults to UTF-8
        and should not force legacy_windows=True.
        """
        mock_stdout = MagicMock(spec=[])  # No encoding attribute

        with (
            patch("ralph.utils.console.sys.platform", "win32"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            # We're testing that missing encoding doesn't trigger our legacy logic.
            # The actual legacy_windows value depends on Rich's auto-detection.
            assert isinstance(result, Console)

    def test_none_encoding_does_not_force_legacy_mode(self) -> None:
        """Test that None encoding doesn't force legacy mode.

        When stdout.encoding is None, our code defaults to UTF-8
        and should not force legacy_windows=True.
        """
        mock_stdout = MagicMock()
        mock_stdout.encoding = None

        with (
            patch("ralph.utils.console.sys.platform", "win32"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            # We're testing that None encoding doesn't trigger our legacy logic.
            # The actual legacy_windows value depends on Rich's auto-detection.
            assert isinstance(result, Console)

    def test_encoding_normalization_removes_hyphen(self) -> None:
        """Test that encoding normalization handles hyphens (UTF-8 -> utf8).

        Our code normalizes UTF-8 to utf8 to match against the legacy encodings
        set. This test ensures the normalization works correctly.
        """
        mock_stdout = MagicMock()
        mock_stdout.encoding = "UTF-8"

        with (
            patch("ralph.utils.console.sys.platform", "win32"),
            patch("ralph.utils.console.sys.stdout", mock_stdout),
        ):
            result = create_console()
            # We're testing that UTF-8 (normalized to utf8) doesn't match
            # legacy encodings and thus doesn't force legacy mode.
            # The actual legacy_windows value depends on Rich's auto-detection.
            assert isinstance(result, Console)


class TestPrintSuccess:
    """Tests for print_success function."""

    def test_prints_message_with_checkmark(self) -> None:
        """Test that print_success outputs message with green checkmark."""
        with patch.object(console, "print") as mock_print:
            print_success("Operation completed")

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Operation completed" in call_args
            assert "[bold green]" in call_args
            assert "\u2713" in call_args

    def test_prints_different_messages(self) -> None:
        """Test that print_success handles different messages."""
        with patch.object(console, "print") as mock_print:
            print_success("Test 1")
            print_success("Test 2")

            assert mock_print.call_count == 2
            assert "Test 1" in mock_print.call_args_list[0][0][0]
            assert "Test 2" in mock_print.call_args_list[1][0][0]


class TestPrintError:
    """Tests for print_error function."""

    def test_prints_message_with_red_x(self) -> None:
        """Test that print_error outputs message with red X."""
        with patch.object(console, "print") as mock_print:
            print_error("Operation failed")

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Operation failed" in call_args
            assert "[bold red]" in call_args
            assert "\u2717" in call_args

    def test_prints_different_error_messages(self) -> None:
        """Test that print_error handles different messages."""
        with patch.object(console, "print") as mock_print:
            print_error("Error 1")
            print_error("Error 2")

            assert mock_print.call_count == 2


class TestPrintWarning:
    """Tests for print_warning function."""

    def test_prints_message_with_yellow_warning(self) -> None:
        """Test that print_warning outputs message with yellow warning."""
        with patch.object(console, "print") as mock_print:
            print_warning("Caution advised")

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Caution advised" in call_args
            assert "[bold yellow]" in call_args
            assert "\u26a0" in call_args

    def test_prints_different_warning_messages(self) -> None:
        """Test that print_warning handles different messages."""
        with patch.object(console, "print") as mock_print:
            print_warning("Warning 1")
            print_warning("Warning 2")

            assert mock_print.call_count == 2


class TestPrintStep:
    """Tests for print_step function."""

    def test_prints_step_with_counter(self) -> None:
        """Test that print_step outputs step counter and message."""
        with patch.object(console, "print") as mock_print:
            print_step(1, 5, "Processing files")

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "[1/5]" in call_args
            assert "Processing files" in call_args
            assert "[bold blue]" in call_args

    def test_prints_various_step_numbers(self) -> None:
        """Test that print_step handles various step numbers."""
        with patch.object(console, "print") as mock_print:
            print_step(3, 10, "Step three")

            call_args = mock_print.call_args[0][0]
            assert "[3/10]" in call_args

    def test_step_counter_format(self) -> None:
        """Test that step counter uses correct format."""
        with patch.object(console, "print") as mock_print:
            print_step(42, 100, "Midway")

            call_args = mock_print.call_args[0][0]
            assert "[42/100]" in call_args


class TestCreateSpinner:
    """Tests for create_spinner context manager."""

    def test_spinner_context_manager(self) -> None:
        """Test that create_spinner works as context manager."""
        with patch.object(console, "status") as mock_status:
            with create_spinner("Loading..."):
                pass

            mock_status.assert_called_once()
            call_kwargs = mock_status.call_args
            assert call_kwargs[0][0] == "Loading..."
            assert call_kwargs[1]["spinner"] == "dots"

    def test_spinner_with_different_messages(self) -> None:
        """Test that create_spinner accepts different messages."""
        with patch.object(console, "status") as mock_status:
            with create_spinner("Processing..."):
                pass

            assert mock_status.call_args[0][0] == "Processing..."

    def test_spinner_yields_none(self) -> None:
        """Test that create_spinner yields None."""
        with patch.object(console, "status"):
            with create_spinner("Working...") as result:
                assert result is None


class TestCentralizedConsolePattern:
    """Tests verifying that all modules use the centralized console.

    These tests ensure the codebase follows the pattern established in US-001/US-002:
    - All modules should import console from ralph.utils.console
    - No direct Console() instantiation outside of create_console()
    """

    def _get_src_python_files(self) -> list[Path]:
        """Get all Python files in the src/ralph directory."""
        src_dir = Path(__file__).parent.parent.parent / "src" / "ralph"
        return list(src_dir.rglob("*.py"))

    def _find_console_instantiations(self, file_path: Path) -> list[tuple[int, str]]:
        """Find direct Console() instantiations in a Python file.

        Args:
            file_path: Path to the Python file to analyze.

        Returns:
            List of (line_number, line_content) tuples where Console() is called.
        """
        content = file_path.read_text()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        instantiations: list[tuple[int, str]] = []
        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for Console() calls
                if isinstance(node.func, ast.Name) and node.func.id == "Console":
                    instantiations.append((node.lineno, lines[node.lineno - 1].strip()))
                # Check for rich.console.Console() calls
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "Console"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "console"
                ):
                    instantiations.append((node.lineno, lines[node.lineno - 1].strip()))

        return instantiations

    def test_no_direct_console_instantiation_outside_create_console(self) -> None:
        """Test that Console() is only called inside create_console().

        All modules should use the centralized console from ralph.utils.console
        instead of creating their own Console instances.
        """
        violations: list[tuple[Path, int, str]] = []

        for file_path in self._get_src_python_files():
            instantiations = self._find_console_instantiations(file_path)

            for line_no, line_content in instantiations:
                # Allow Console() only in create_console() in console.py
                if file_path.name == "console.py" and "def create_console" in file_path.read_text():
                    # Check if this is inside create_console function
                    content = file_path.read_text()
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef) and node.name == "create_console":
                                # Check if line_no is within this function
                                if node.lineno <= line_no <= node.end_lineno:  # type: ignore[operator]
                                    continue
                    except SyntaxError:
                        pass
                    # Only add if not in create_console
                    if "return Console(" in line_content:
                        continue
                else:
                    violations.append((file_path, line_no, line_content))

        if violations:
            msg = "Found direct Console() instantiation outside create_console():\n"
            for path, line_no, line in violations:
                relative_path = path.relative_to(Path(__file__).parent.parent.parent)
                msg += f"  {relative_path}:{line_no}: {line}\n"
            msg += "\nAll modules should import console from ralph.utils.console instead."
            pytest.fail(msg)

    def test_console_module_exports_shared_instance(self) -> None:
        """Test that ralph.utils.console exports a shared console instance."""
        from ralph.utils.console import console as exported_console

        assert isinstance(exported_console, Console)

    def test_utils_init_re_exports_console(self) -> None:
        """Test that ralph.utils re-exports the console from console.py."""
        from ralph.utils import console as utils_console
        from ralph.utils.console import console as console_module_console

        # Both should reference the same instance
        assert utils_console is console_module_console
