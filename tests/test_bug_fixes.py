"""Unit tests for bug fixes in Ralph CLI v1.2.

This module contains comprehensive tests for the bug fixes implemented
in the v1.2 release, ensuring regression prevention.

Test Coverage:
- US-001: _build_base_args() verbose flag when streaming
- US-002: _parse_stream_event() newline markers
- US-003: run_interactive() skip_permissions parameter
- US-007: PROGRESS.txt archival timestamp format
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph.commands.tasks import PROGRESS_TEMPLATE, _archive_progress_file
from ralph.services.claude import MESSAGE_BOUNDARY, ClaudeService


class TestBuildBaseArgsStreamingVerbose:
    """Tests for _build_base_args() verbose flag behavior when streaming.

    Bug fix: US-001 - stream-json output format requires --verbose flag.
    When streaming is enabled, --verbose must always be included in args.
    """

    def test_verbose_included_when_streaming_enabled(self) -> None:
        """Test that --verbose is always included when stream=True.

        This is the core bug fix test - streaming requires --verbose
        for the stream-json format to work properly.
        """
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("test prompt", stream=True)

            args = mock_run.call_args[0][0]
            assert "--verbose" in args, "--verbose should be included when streaming"

    def test_verbose_included_even_when_service_verbose_false(self) -> None:
        """Test that --verbose is added for streaming even if service.verbose=False."""
        service = ClaudeService(verbose=False)

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=True)

            args = mock_run.call_args[0][0]
            assert "--verbose" in args

    def test_verbose_not_duplicated_when_service_verbose_true(self) -> None:
        """Test that --verbose is not duplicated when service.verbose=True.

        Both service.verbose=True and stream=True would add --verbose,
        but the code should check to avoid duplication.
        """
        service = ClaudeService(verbose=True)

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=True)

            args = mock_run.call_args[0][0]
            verbose_count = args.count("--verbose")
            assert verbose_count == 1, f"Expected exactly 1 --verbose, got {verbose_count}"

    def test_verbose_not_added_when_not_streaming_and_service_not_verbose(self) -> None:
        """Test that --verbose is NOT included when stream=False and verbose=False."""
        service = ClaudeService(verbose=False)

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=False)

            args = mock_run.call_args[0][0]
            assert "--verbose" not in args, (
                "--verbose should not be included when not streaming and not verbose"
            )

    def test_stream_json_format_only_added_when_streaming(self) -> None:
        """Test that --output-format stream-json is only added when streaming."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            # When streaming
            service.run_print_mode("prompt", stream=True)
            args_streaming = mock_run.call_args[0][0]
            assert "--output-format" in args_streaming
            fmt_idx = args_streaming.index("--output-format")
            assert args_streaming[fmt_idx + 1] == "stream-json"

            # When not streaming
            service.run_print_mode("prompt", stream=False)
            args_not_streaming = mock_run.call_args[0][0]
            assert "--output-format" not in args_not_streaming

    def test_verbose_and_stream_json_combined_correctly(self) -> None:
        """Test that --verbose and --output-format stream-json are both present."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("prompt", stream=True)

            args = mock_run.call_args[0][0]
            assert "--verbose" in args
            assert "--output-format" in args
            assert "stream-json" in args


class TestParseStreamEventNewlineMarkers:
    """Tests for _parse_stream_event() newline marker behavior.

    Bug fix: US-002 - Add newlines between message blocks in output.
    Bug fix: Issue #6 - Output formatting with newlines between content blocks.

    The parser should return MESSAGE_BOUNDARY for:
    - content_block_stop: end of each content block within a message
    - message_stop: end of the entire message
    - result: end of the conversation
    """

    def test_content_block_stop_returns_newline_marker(self) -> None:
        """Test that content_block_stop events return MESSAGE_BOUNDARY.

        This is the key fix for issue #6 - content_block_stop fires after each
        content block (text, tool_use), enabling proper newlines between
        Claude's thoughts within a single message.
        """
        service = ClaudeService()

        line = '{"type":"content_block_stop","index":0}'
        result = service._parse_stream_event(line)

        assert result == MESSAGE_BOUNDARY
        assert result == "\n"

    def test_message_stop_returns_newline_marker(self) -> None:
        """Test that message_stop events return MESSAGE_BOUNDARY."""
        service = ClaudeService()

        line = '{"type":"message_stop"}'
        result = service._parse_stream_event(line)

        assert result == MESSAGE_BOUNDARY
        assert result == "\n"

    def test_result_event_returns_newline_marker(self) -> None:
        """Test that result events return MESSAGE_BOUNDARY."""
        service = ClaudeService()

        line = '{"type":"result","subtype":"success","result":{"foo":"bar"}}'
        result = service._parse_stream_event(line)

        assert result == MESSAGE_BOUNDARY

    def test_message_boundary_constant_is_newline(self) -> None:
        """Test that MESSAGE_BOUNDARY constant is exactly a newline."""
        assert MESSAGE_BOUNDARY == "\n"
        assert len(MESSAGE_BOUNDARY) == 1

    def test_text_delta_does_not_return_newline_marker(self) -> None:
        """Test that text_delta events return the text, not a newline marker."""
        service = ClaudeService()

        line = '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}'
        result = service._parse_stream_event(line)

        assert result == "Hello"
        assert result != MESSAGE_BOUNDARY

    def test_assistant_message_returns_text_with_newline(self) -> None:
        """Test that assistant messages with text return text with trailing newline."""
        service = ClaudeService()

        line = '{"type":"assistant","message":{"content":[{"type":"text","text":"Response"}]}}'
        result = service._parse_stream_event(line)

        # Assistant events get trailing newline for readability between turns
        assert result == "Response\n"
        assert result != MESSAGE_BOUNDARY  # It's text + newline, not just newline

    def test_tool_use_events_return_none(self) -> None:
        """Test that tool_use events return None (not written to output)."""
        service = ClaudeService()

        line = '{"type":"tool_use","id":"toolu_123","name":"Read","input":{}}'
        result = service._parse_stream_event(line)

        assert result is None

    def test_tool_result_events_return_none(self) -> None:
        """Test that tool_result events return None."""
        service = ClaudeService()

        line = '{"type":"tool_result","tool_use_id":"toolu_123","content":"file contents"}'
        result = service._parse_stream_event(line)

        assert result is None

    def test_stream_output_writes_newline_at_message_boundary(self) -> None:
        """Test that _stream_output writes newlines at message boundaries.

        Integration test for the full flow: events are parsed, and message
        boundaries result in newlines being written to output.
        """
        mock_stdout = MagicMock()
        service = ClaudeService()
        object.__setattr__(service, "stdout", mock_stdout)

        mock_process = MagicMock()
        mock_process.stdout = iter(
            [
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"First"}}\n',
                '{"type":"message_stop"}\n',
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Second"}}\n',
            ]
        )
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = ""

        stdout_content, _ = service._stream_output(mock_process, parse_json=True)

        # Should have newline between First and Second
        assert stdout_content == "First\nSecond"
        # Verify the newline was written
        mock_stdout.write.assert_any_call("\n")

    def test_stream_output_writes_newline_at_content_block_stop(self) -> None:
        """Test that _stream_output writes newlines at content_block_stop.

        Issue #6 fix: Multiple content blocks within a single message should be
        separated by newlines. The stream-json format emits content_block_stop
        after each block (text or tool_use), which triggers the newline.

        Example stream structure:
        content_block_start (text)
        content_block_delta (text: "I'll check...")
        content_block_stop     <- newline here
        content_block_start (tool_use)
        content_block_delta (tool input)
        content_block_stop     <- newline here
        """
        mock_stdout = MagicMock()
        service = ClaudeService()
        object.__setattr__(service, "stdout", mock_stdout)

        # Realistic scenario: text block, then tool use, then more text
        mock_process = MagicMock()
        evt1 = '{"type":"content_block_delta",'
        evt1 += '"delta":{"type":"text_delta","text":"Let me check."}}\n'
        evt2 = '{"type":"content_block_stop","index":0}\n'
        evt3 = '{"type":"content_block_start","index":1,'
        evt3 += '"content_block":{"type":"tool_use"}}\n'
        evt4 = '{"type":"content_block_stop","index":1}\n'
        evt5 = '{"type":"content_block_delta",'
        evt5 += '"delta":{"type":"text_delta","text":"Now implementing."}}\n'
        evt6 = '{"type":"content_block_stop","index":2}\n'
        mock_process.stdout = iter([evt1, evt2, evt3, evt4, evt5, evt6])
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = ""

        stdout_content, _ = service._stream_output(mock_process, parse_json=True)

        # Expected output with newlines between content blocks
        # 3 content_block_stop events = 3 newlines
        expected = "Let me check.\n\nNow implementing.\n"
        assert stdout_content == expected

        # Verify structure: text, newline, newline, text, newline
        calls = [call[0][0] for call in mock_stdout.write.call_args_list]
        assert "Let me check." in calls
        assert "Now implementing." in calls
        assert calls.count("\n") == 3  # 3 content_block_stop events


class TestRunInteractiveSkipPermissions:
    """Tests for run_interactive() skip_permissions parameter.

    Bug fix: US-003 - Enable skip permissions for ralph prd.
    The run_interactive() method should accept skip_permissions parameter.
    """

    def test_skip_permissions_adds_flag_when_true(self) -> None:
        """Test that skip_permissions=True adds --dangerously-skip-permissions."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive(skip_permissions=True)

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" in args

    def test_skip_permissions_flag_not_added_when_false(self) -> None:
        """Test that skip_permissions=False does NOT add the flag."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive(skip_permissions=False)

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" not in args

    def test_skip_permissions_defaults_to_false(self) -> None:
        """Test that skip_permissions defaults to False."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive()

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" not in args

    def test_skip_permissions_works_with_prompt(self) -> None:
        """Test that skip_permissions works correctly with a prompt."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive(prompt="Hello", skip_permissions=True)

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" in args
            assert "Hello" in args

    def test_skip_permissions_works_with_verbose(self) -> None:
        """Test that skip_permissions works with verbose service."""
        service = ClaudeService(verbose=True)

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive(skip_permissions=True)

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" in args
            assert "--verbose" in args

    def test_skip_permissions_flag_position(self) -> None:
        """Test that skip_permissions flag appears before the prompt."""
        service = ClaudeService()

        with patch("ralph.services.claude.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            service.run_interactive(prompt="my prompt", skip_permissions=True)

            args = mock_run.call_args[0][0]
            skip_idx = args.index("--dangerously-skip-permissions")
            prompt_idx = args.index("my prompt")
            assert skip_idx < prompt_idx, "skip_permissions flag should appear before prompt"


class TestProgressArchivalTimestampFormat:
    """Tests for PROGRESS.txt archival timestamp format.

    Bug fix: US-007 - Archive PROGRESS.txt on new task generation.
    The timestamp format should be YYYYMMDD_HHMMSS.
    """

    def test_archive_creates_file_with_timestamp_format(self, tmp_path: Path) -> None:
        """Test that archived file uses YYYYMMDD_HHMMSS format."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("# Original content")

        result = _archive_progress_file(tmp_path)

        assert result is not None
        # Pattern: PROGRESS.YYYYMMDD_HHMMSS.txt
        pattern = r"^PROGRESS\.\d{8}_\d{6}\.txt$"
        assert re.match(pattern, result.name), (
            f"Archive filename {result.name} does not match YYYYMMDD_HHMMSS format"
        )

    def test_archive_timestamp_is_valid_datetime(self, tmp_path: Path) -> None:
        """Test that the timestamp in archive filename is a valid datetime."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("# Content")

        result = _archive_progress_file(tmp_path)

        assert result is not None
        # Extract timestamp from filename
        match = re.search(r"PROGRESS\.(\d{8}_\d{6})\.txt", result.name)
        assert match is not None
        timestamp_str = match.group(1)

        # Parse and validate the timestamp
        parsed = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        assert parsed is not None

        # Should be recent (within last minute)
        now = datetime.now(UTC).replace(tzinfo=None)
        diff = abs((now - parsed).total_seconds())
        assert diff < 60, "Timestamp should be within the last minute"

    def test_archive_preserves_original_content(self, tmp_path: Path) -> None:
        """Test that archived file contains the original content."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        original_content = "# Progress Log\n\n## US-001\nCompleted the story\n\nDetails here."
        (plans_dir / "PROGRESS.txt").write_text(original_content)

        result = _archive_progress_file(tmp_path)

        assert result is not None
        assert result.read_text() == original_content

    def test_archive_creates_fresh_progress_with_template(self, tmp_path: Path) -> None:
        """Test that fresh PROGRESS.txt is created with standard template."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("# Old content")

        _archive_progress_file(tmp_path)

        new_progress = plans_dir / "PROGRESS.txt"
        assert new_progress.exists()
        content = new_progress.read_text()
        assert content == PROGRESS_TEMPLATE

    def test_archive_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that archive returns None if PROGRESS.txt doesn't exist."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        # Don't create PROGRESS.txt

        result = _archive_progress_file(tmp_path)

        assert result is None

    def test_archive_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        """Test that archive returns None if PROGRESS.txt is empty."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("")

        result = _archive_progress_file(tmp_path)

        assert result is None

    def test_archive_returns_none_for_whitespace_only(self, tmp_path: Path) -> None:
        """Test that archive returns None if PROGRESS.txt contains only whitespace."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("   \n\n  \t  \n")

        result = _archive_progress_file(tmp_path)

        assert result is None

    def test_fresh_progress_has_codebase_patterns_section(self, tmp_path: Path) -> None:
        """Test that fresh PROGRESS.txt includes Codebase Patterns section."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("# Old content")

        _archive_progress_file(tmp_path)

        content = (plans_dir / "PROGRESS.txt").read_text()
        assert "## Codebase Patterns" in content

    def test_fresh_progress_has_log_section(self, tmp_path: Path) -> None:
        """Test that fresh PROGRESS.txt includes Log section."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("# Old content")

        _archive_progress_file(tmp_path)

        content = (plans_dir / "PROGRESS.txt").read_text()
        assert "## Log" in content


class TestBugFixesIntegration:
    """Integration tests verifying bug fixes work together correctly."""

    def test_streaming_with_message_boundaries_output(self) -> None:
        """Test that streaming output correctly handles message boundaries.

        This verifies the integration of:
        - _build_base_args adding --verbose for streaming
        - _parse_stream_event detecting message boundaries
        - _stream_output writing newlines at boundaries
        """
        mock_stdout = MagicMock()
        service = ClaudeService()
        object.__setattr__(service, "stdout", mock_stdout)

        # Simulate a realistic streaming session with multiple messages
        mock_process = MagicMock()
        event1 = (
            '{"type":"assistant","message":{"content":[{"type":"text","text":"First message"}]}}\n'
        )
        event2 = '{"type":"message_stop"}\n'
        event3 = '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Second "}}\n'
        event4 = '{"type":"content_block_delta","delta":{"type":"text_delta","text":"message"}}\n'
        event5 = '{"type":"result","subtype":"success"}\n'
        mock_process.stdout = iter([event1, event2, event3, event4, event5])
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = ""

        stdout_content, _ = service._stream_output(mock_process, parse_json=True)

        # Content should have newlines at message boundaries
        assert "First message" in stdout_content
        assert "Second message" in stdout_content
        # Should have newline between first and second
        assert "\n" in stdout_content

    def test_verbose_flag_in_streaming_args_order(self) -> None:
        """Test that verbose flag is positioned correctly in streaming args."""
        service = ClaudeService()

        with patch.object(service, "_run_process") as mock_run:
            mock_run.return_value = ("output", 0)

            service.run_print_mode("my prompt", stream=True)

            args = mock_run.call_args[0][0]
            # claude should be first
            assert args[0] == "claude"
            # --verbose should be present
            assert "--verbose" in args
            # --print should be present
            assert "--print" in args
            # --output-format stream-json should be present
            assert "--output-format" in args
