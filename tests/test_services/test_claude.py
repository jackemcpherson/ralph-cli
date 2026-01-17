"""Tests for Claude service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph.services.claude import ClaudeError, ClaudeService


class TestClaudeServiceInit:
    """Tests for ClaudeService initialization."""

    def test_default_values(self) -> None:
        """Test that ClaudeService has correct default values."""
        service = ClaudeService()

        assert service.working_dir is None
        assert service.verbose is False
        assert service.claude_command == "claude"

    def test_custom_working_dir(self, tmp_path: Path) -> None:
        """Test that working_dir can be customized."""
        service = ClaudeService(working_dir=tmp_path)
        assert service.working_dir == tmp_path

    def test_verbose_flag(self) -> None:
        """Test that verbose flag can be set."""
        service = ClaudeService(verbose=True)
        assert service.verbose is True

    def test_custom_claude_command(self) -> None:
        """Test that claude_command can be customized."""
        service = ClaudeService(claude_command="/custom/path/claude")
        assert service.claude_command == "/custom/path/claude"


class TestBuildBaseArgs:
    """Tests for _build_base_args method."""

    def test_returns_command_name(self) -> None:
        """Test that base args include the claude command."""
        service = ClaudeService()
        args = service._build_base_args()

        assert args == ["claude"]

    def test_includes_verbose_flag_when_enabled(self) -> None:
        """Test that --verbose is included when verbose=True."""
        service = ClaudeService(verbose=True)
        args = service._build_base_args()

        assert args == ["claude", "--verbose"]

    def test_custom_command_used(self) -> None:
        """Test that custom claude_command is used."""
        service = ClaudeService(claude_command="/path/to/claude")
        args = service._build_base_args()

        assert args == ["/path/to/claude"]


class TestRunPrintMode:
    """Tests for run_print_mode method."""

    def test_builds_correct_args_with_prompt(self) -> None:
        """Test that run_print_mode builds correct arguments."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("test prompt")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "claude" in args
            assert "--print" in args
            assert "test prompt" in args

    def test_includes_model_when_specified(self) -> None:
        """Test that --model is included when model is specified."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", model="opus")

            args = mock_run.call_args[0][0]
            assert "--model" in args
            model_idx = args.index("--model")
            assert args[model_idx + 1] == "opus"

    def test_includes_max_turns_when_specified(self) -> None:
        """Test that --max-turns is included when max_turns is specified."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", max_turns=5)

            args = mock_run.call_args[0][0]
            assert "--max-turns" in args
            max_turns_idx = args.index("--max-turns")
            assert args[max_turns_idx + 1] == "5"

    def test_includes_system_prompt_when_specified(self) -> None:
        """Test that --system-prompt is included when system_prompt is specified."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", system_prompt="You are a helpful assistant")

            args = mock_run.call_args[0][0]
            assert "--system-prompt" in args
            sp_idx = args.index("--system-prompt")
            assert args[sp_idx + 1] == "You are a helpful assistant"

    def test_includes_allowed_tools_when_specified(self) -> None:
        """Test that --allowedTools is included for each allowed tool."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", allowed_tools=["Read", "Write", "Bash"])

            args = mock_run.call_args[0][0]
            # Should have --allowedTools three times
            allowed_tools_count = args.count("--allowedTools")
            assert allowed_tools_count == 3
            assert "Read" in args
            assert "Write" in args
            assert "Bash" in args

    def test_stream_passed_to_run_process(self) -> None:
        """Test that stream parameter is passed to _run_process."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=False)

            mock_run.assert_called_once()
            assert mock_run.call_args[0][1] is False

    def test_default_stream_is_true(self) -> None:
        """Test that stream defaults to True."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt")

            mock_run.assert_called_once()
            assert mock_run.call_args[0][1] is True


class TestRunWithOutputFormat:
    """Tests for run_with_output_format method."""

    def test_includes_output_format(self) -> None:
        """Test that --output-format is included."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_with_output_format("prompt", output_format="json")

            args = mock_run.call_args[0][0]
            assert "--output-format" in args
            fmt_idx = args.index("--output-format")
            assert args[fmt_idx + 1] == "json"

    def test_includes_model_and_max_turns(self) -> None:
        """Test that model and max_turns are passed through."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_with_output_format(
                "prompt", output_format="text", model="sonnet", max_turns=10
            )

            args = mock_run.call_args[0][0]
            assert "--model" in args
            assert "sonnet" in args
            assert "--max-turns" in args
            assert "10" in args


class TestRunInteractive:
    """Tests for run_interactive method."""

    def test_runs_claude_without_prompt(self) -> None:
        """Test that run_interactive calls subprocess correctly."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = service.run_interactive()

            assert result == 0
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args == ["claude"]

    def test_runs_claude_with_prompt(self) -> None:
        """Test that run_interactive passes prompt as argument."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive(prompt="Hello Claude")

            args = mock_run.call_args[0][0]
            assert "Hello Claude" in args

    def test_verbose_flag_included(self) -> None:
        """Test that verbose flag is passed when enabled."""
        service = ClaudeService(verbose=True)

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive()

            args = mock_run.call_args[0][0]
            assert "--verbose" in args

    def test_raises_claude_error_when_not_found(self) -> None:
        """Test that ClaudeError is raised when Claude CLI not found."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(ClaudeError) as exc_info:
                service.run_interactive()

            assert "Claude Code CLI not found" in str(exc_info.value)

    def test_raises_claude_error_on_subprocess_error(self) -> None:
        """Test that ClaudeError is raised on subprocess error."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Process failed")

            with pytest.raises(ClaudeError) as exc_info:
                service.run_interactive()

            assert "Failed to run Claude Code" in str(exc_info.value)


class TestRunProcess:
    """Tests for _run_process method."""

    def test_raises_claude_error_when_not_found(self) -> None:
        """Test that ClaudeError is raised when Claude CLI not found."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError()

            with pytest.raises(ClaudeError) as exc_info:
                service._run_process(["claude", "--print", "test"], stream=False)

            assert "Claude Code CLI not found" in str(exc_info.value)

    def test_raises_claude_error_on_subprocess_error(self) -> None:
        """Test that ClaudeError is raised on subprocess error."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = subprocess.SubprocessError("Failed")

            with pytest.raises(ClaudeError) as exc_info:
                service._run_process(["claude", "--print", "test"], stream=False)

            assert "Failed to run Claude Code" in str(exc_info.value)

    def test_non_streaming_captures_output(self) -> None:
        """Test that non-streaming mode captures output correctly."""
        service = ClaudeService()

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("stdout content", "stderr content")
        mock_process.wait.return_value = 0

        with patch("ralph.services.claude.subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_process

            output, code = service._run_process(["claude", "-p", "test"], stream=False)

            assert output == "stdout content"
            assert code == 0


class TestClaudeError:
    """Tests for ClaudeError exception."""

    def test_error_message(self) -> None:
        """Test that ClaudeError stores message correctly."""
        error = ClaudeError("Test error")
        assert str(error) == "Test error"

    def test_is_exception_subclass(self) -> None:
        """Test that ClaudeError is an Exception subclass."""
        assert issubclass(ClaudeError, Exception)
