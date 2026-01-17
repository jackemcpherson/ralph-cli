"""Tests for console utilities."""

from unittest.mock import patch

from rich.console import Console

from ralph.utils.console import (
    console,
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
