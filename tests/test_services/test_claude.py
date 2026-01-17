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

    def test_includes_skip_permissions_when_true(self) -> None:
        """Test that --dangerously-skip-permissions is included when skip_permissions=True."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", skip_permissions=True)

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" in args

    def test_excludes_skip_permissions_when_false(self) -> None:
        """Test that --dangerously-skip-permissions is NOT included when skip_permissions=False."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", skip_permissions=False)

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" not in args

    def test_default_skip_permissions_is_false(self) -> None:
        """Test that skip_permissions defaults to False."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt")

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" not in args

    def test_includes_append_system_prompt_when_specified(self) -> None:
        """Test that --append-system-prompt is included when append_system_prompt is provided."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", append_system_prompt="Do not ask for permission")

            args = mock_run.call_args[0][0]
            assert "--append-system-prompt" in args
            asp_idx = args.index("--append-system-prompt")
            assert args[asp_idx + 1] == "Do not ask for permission"

    def test_excludes_append_system_prompt_when_none(self) -> None:
        """Test that --append-system-prompt is NOT included when append_system_prompt is None."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", append_system_prompt=None)

            args = mock_run.call_args[0][0]
            assert "--append-system-prompt" not in args

    def test_default_append_system_prompt_is_none(self) -> None:
        """Test that append_system_prompt defaults to None."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt")

            args = mock_run.call_args[0][0]
            assert "--append-system-prompt" not in args

    def test_includes_stream_json_format_when_streaming(self) -> None:
        """Test that --output-format stream-json is included when stream=True."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=True)

            args = mock_run.call_args[0][0]
            assert "--output-format" in args
            fmt_idx = args.index("--output-format")
            assert args[fmt_idx + 1] == "stream-json"

    def test_excludes_stream_json_format_when_not_streaming(self) -> None:
        """Test that --output-format stream-json is NOT included when stream=False."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=False)

            args = mock_run.call_args[0][0]
            assert "--output-format" not in args


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

    def test_streaming_passes_parse_json_to_stream_output(self) -> None:
        """Test that _run_process passes parse_json to _stream_output when streaming."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.Popen"):
            with patch.object(service, "_stream_output") as mock_stream:
                mock_stream.return_value = ("output", "")

                service._run_process(["claude", "-p", "test"], stream=True, parse_json=True)

                # Verify parse_json was passed
                mock_stream.assert_called_once()
                call_kwargs = mock_stream.call_args.kwargs
                assert call_kwargs.get("parse_json") is True


class TestRunPrintModeStreamJsonParsing:
    """Tests for run_print_mode stream-json parsing integration."""

    def test_run_print_mode_passes_parse_json_when_streaming(self) -> None:
        """Test that run_print_mode passes parse_json=True when stream=True."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=True)

            # Verify parse_json was passed as True
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs.get("parse_json") is True

    def test_run_print_mode_passes_parse_json_false_when_not_streaming(self) -> None:
        """Test that run_print_mode passes parse_json=False when stream=False."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=False)

            # Verify parse_json was passed as False
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs.get("parse_json") is False


class TestStreamOutput:
    """Tests for _stream_output method."""

    def test_stream_output_writes_lines_when_not_parsing(self) -> None:
        """Test that _stream_output writes raw lines when parse_json=False."""
        mock_stdout = MagicMock()
        service = ClaudeService()
        # Replace stdout with mock after initialization
        object.__setattr__(service, "stdout", mock_stdout)

        mock_process = MagicMock()
        mock_process.stdout = iter(["line1\n", "line2\n"])
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = ""

        stdout_content, _ = service._stream_output(mock_process, parse_json=False)

        assert stdout_content == "line1\nline2\n"
        # Verify lines were written
        assert mock_stdout.write.call_count == 2
        mock_stdout.write.assert_any_call("line1\n")
        mock_stdout.write.assert_any_call("line2\n")

    def test_stream_output_parses_json_when_enabled(self) -> None:
        """Test that _stream_output parses JSON and extracts text when parse_json=True."""
        mock_stdout = MagicMock()
        service = ClaudeService()
        object.__setattr__(service, "stdout", mock_stdout)

        mock_process = MagicMock()
        mock_process.stdout = iter(
            [
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello "}}\n',
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"world"}}\n',
            ]
        )
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = ""

        stdout_content, _ = service._stream_output(mock_process, parse_json=True)

        assert stdout_content == "Hello world"
        # Verify parsed text was written
        mock_stdout.write.assert_any_call("Hello ")
        mock_stdout.write.assert_any_call("world")

    def test_stream_output_skips_non_text_events_when_parsing(self) -> None:
        """Test that _stream_output skips non-text events when parse_json=True."""
        mock_stdout = MagicMock()
        service = ClaudeService()
        object.__setattr__(service, "stdout", mock_stdout)

        mock_process = MagicMock()
        mock_process.stdout = iter(
            [
                '{"type":"tool_use","name":"Read"}\n',
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"text"}}\n',
                '{"type":"tool_result"}\n',
            ]
        )
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = ""

        stdout_content, _ = service._stream_output(mock_process, parse_json=True)

        assert stdout_content == "text"
        # Should only have written once (the text event)
        mock_stdout.write.assert_called_once_with("text")


class TestParseStreamEvent:
    """Tests for _parse_stream_event method."""

    def test_parses_assistant_message_with_text(self) -> None:
        """Test that assistant messages with text content are parsed."""
        service = ClaudeService()

        line = '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello world"}]}}'
        result = service._parse_stream_event(line)

        assert result == "Hello world"

    def test_parses_content_block_delta(self) -> None:
        """Test that content_block_delta events are parsed."""
        service = ClaudeService()

        line = '{"type":"content_block_delta","delta":{"type":"text_delta","text":"chunk"}}'
        result = service._parse_stream_event(line)

        assert result == "chunk"

    def test_returns_none_for_non_text_events(self) -> None:
        """Test that non-text events return None."""
        service = ClaudeService()

        line = '{"type":"tool_use","name":"Read"}'
        result = service._parse_stream_event(line)

        assert result is None

    def test_returns_none_for_invalid_json(self) -> None:
        """Test that invalid JSON returns None."""
        service = ClaudeService()

        line = "not valid json"
        result = service._parse_stream_event(line)

        assert result is None

    def test_returns_none_for_empty_content_array(self) -> None:
        """Test that empty content array returns None."""
        service = ClaudeService()

        line = '{"type":"assistant","message":{"content":[]}}'
        result = service._parse_stream_event(line)

        assert result is None

    def test_returns_none_for_non_text_content_type(self) -> None:
        """Test that non-text content type returns None."""
        service = ClaudeService()

        line = '{"type":"assistant","message":{"content":[{"type":"tool_use"}]}}'
        result = service._parse_stream_event(line)

        assert result is None

    def test_handles_missing_delta_type(self) -> None:
        """Test that content_block_delta without text_delta type returns None."""
        service = ClaudeService()

        line = '{"type":"content_block_delta","delta":{"type":"other","data":"stuff"}}'
        result = service._parse_stream_event(line)

        assert result is None


class TestClaudeError:
    """Tests for ClaudeError exception."""

    def test_error_message(self) -> None:
        """Test that ClaudeError stores message correctly."""
        error = ClaudeError("Test error")
        assert str(error) == "Test error"

    def test_is_exception_subclass(self) -> None:
        """Test that ClaudeError is an Exception subclass."""
        assert issubclass(ClaudeError, Exception)
