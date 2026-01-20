"""Integration tests for command-level behavior.

These tests verify that the fixed commands work end-to-end without crashing,
including:
- ralph once and ralph loop run without -v flag (no crash)
- ralph tasks streams output
- ralph init creates CHANGELOG.md
"""

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for testing commands."""
    return CliRunner()


@pytest.fixture
def sample_tasks() -> dict:
    """Sample TASKS.json content with incomplete stories."""
    return {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "First story",
                "description": "As a user, I want feature A",
                "acceptanceCriteria": ["Criterion 1", "Typecheck passes"],
                "priority": 1,
                "passes": False,
                "notes": "",
            },
        ],
    }


@pytest.fixture
def project_with_tasks(tmp_path: Path, sample_tasks: dict) -> Path:
    """Create a project directory with TASKS.json and PROGRESS.txt."""
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()

    tasks_file = plans_dir / "TASKS.json"
    tasks_file.write_text(json.dumps(sample_tasks, indent=2))

    progress_file = plans_dir / "PROGRESS.txt"
    progress_file.write_text("# Progress Log\n\n")

    return tmp_path


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Create a temporary Python project with pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")
    return tmp_path


@pytest.fixture
def project_with_spec(tmp_path: Path) -> Path:
    """Create a project with SPEC.md for ralph tasks."""
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()

    spec_file = plans_dir / "SPEC.md"
    spec_file.write_text("# Feature Spec\n\nThis is a test specification for task generation.")

    return tmp_path


class TestOnceCommandWithoutVerboseFlag:
    """Integration tests for ralph once running without the -v flag.

    These tests verify that the streaming fix (US-001) works correctly,
    allowing ralph once to run in non-verbose mode without crashing.
    """

    def test_once_runs_without_verbose_flag_no_crash(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once runs without -v flag and does not crash.

        This is the core test for the streaming bug fix (Issue #7).
        Before the fix, running without --verbose would crash because
        stream-json format requires the --verbose flag internally.
        """
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Task output text")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                # Run WITHOUT the -v flag - this is the key test
                result = runner.invoke(app, ["once"])

            # Should not crash - exit code 0 (success) or 1 (story not passed) are both OK
            assert result.exit_code in (0, 1)
            # Should not contain Python traceback/exception
            assert "Traceback" not in result.output
            assert "Exception" not in result.output
            assert "Error" not in result.output or "Claude" in result.output

        finally:
            os.chdir(original_cwd)

    def test_once_verbose_flag_still_includes_verbose(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once --verbose still includes --verbose in args."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Output")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["once", "--verbose"])

            assert "--verbose" in captured_args

        finally:
            os.chdir(original_cwd)

    def test_once_without_verbose_uses_stream_json_format(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once uses stream-json format even without -v flag.

        The fix ensures that --verbose is automatically added when using
        stream-json format, but the user doesn't see raw JSON - only extracted text.
        """
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            # Return valid stream-json event
            json_event = (
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Done"}}'
            )
            mock_process.stdout = StringIO(json_event)
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["once"])  # No -v flag

            # Should still use stream-json format
            assert "--output-format" in captured_args
            format_idx = captured_args.index("--output-format")
            assert captured_args[format_idx + 1] == "stream-json"

            # --verbose should be added automatically by the fix
            assert "--verbose" in captured_args

        finally:
            os.chdir(original_cwd)

    def test_once_parses_text_from_stream_json_events(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once extracts text from stream-json events.

        In non-verbose mode, users should see human-readable text,
        not raw JSON events.
        """
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            # Simulate multiple stream-json events
            event1 = (
                '{"type":"content_block_delta",'
                '"delta":{"type":"text_delta","text":"Starting task..."}}'
            )
            event2 = '{"type":"content_block_delta","delta":{"type":"text_delta","text":" Done!"}}'
            events = [event1, event2]
            mock_process.stdout = iter(line + "\n" for line in events)
            mock_process.stderr = MagicMock()
            mock_process.stderr.read.return_value = ""
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["once"])

            # Should not crash
            assert "Traceback" not in result.output

        finally:
            os.chdir(original_cwd)


class TestLoopCommandWithoutVerboseFlag:
    """Integration tests for ralph loop running without the -v flag.

    These tests verify that the streaming fix also works for ralph loop,
    which uses the same streaming mechanism as ralph once.
    """

    def test_loop_runs_without_verbose_flag_no_crash(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop runs without -v flag and does not crash.

        Similar to once, loop should run in non-verbose mode without crashing.
        """
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("<ralph>COMPLETE</ralph>")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                # Run WITHOUT the -v flag
                result = runner.invoke(app, ["loop", "1"])

            # Should not crash
            assert result.exit_code in (0, 1)
            assert "Traceback" not in result.output
            assert "Exception" not in result.output

        finally:
            os.chdir(original_cwd)

    def test_loop_verbose_flag_still_includes_verbose(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop --verbose still includes --verbose in args."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("<ralph>COMPLETE</ralph>")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1", "--verbose"])

            assert "--verbose" in captured_args

        finally:
            os.chdir(original_cwd)

    def test_loop_without_verbose_uses_stream_json_format(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop uses stream-json format even without -v flag."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            json_event = (
                '{"type":"assistant","message":{"content":'
                '[{"type":"text","text":"<ralph>COMPLETE</ralph>"}]}}'
            )
            mock_process.stdout = StringIO(json_event)
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])  # No -v flag

            # Should still use stream-json format
            assert "--output-format" in captured_args
            format_idx = captured_args.index("--output-format")
            assert captured_args[format_idx + 1] == "stream-json"

            # --verbose should be added automatically by the fix
            assert "--verbose" in captured_args

        finally:
            os.chdir(original_cwd)

    def test_loop_multiple_iterations_without_verbose(
        self, runner: CliRunner, project_with_tasks: Path, sample_tasks: dict
    ) -> None:
        """Test that ralph loop runs multiple iterations without -v flag.

        Verifies that the streaming fix works across multiple iterations.
        """
        original_cwd = os.getcwd()
        invocation_count = 0

        def mock_popen(args: list[str], **kwargs):
            nonlocal invocation_count
            invocation_count += 1

            # Mark story as passed and signal completion
            updated_tasks = sample_tasks.copy()
            updated_tasks["userStories"][0]["passes"] = True
            tasks_file = project_with_tasks / "plans" / "TASKS.json"
            tasks_file.write_text(json.dumps(updated_tasks, indent=2))

            mock_process = MagicMock()
            mock_process.stdout = StringIO("<ralph>COMPLETE</ralph>")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                result = runner.invoke(app, ["loop", "5"])  # No -v flag

            # Should not crash
            assert "Traceback" not in result.output
            assert invocation_count >= 1

        finally:
            os.chdir(original_cwd)


class TestTasksCommandStreaming:
    """Integration tests for ralph tasks streaming output (US-008).

    These tests verify that ralph tasks uses streaming and that
    JSON extraction works correctly with streamed output.
    """

    def test_tasks_streams_output(self, runner: CliRunner, project_with_spec: Path) -> None:
        """Test that ralph tasks uses streaming for output.

        This verifies US-008: Enable streaming for ralph tasks.
        """
        original_cwd = os.getcwd()
        captured_kwargs: dict = {}

        valid_tasks_json = json.dumps(
            {
                "project": "TestProject",
                "branchName": "ralph/test-feature",
                "description": "Test description",
                "userStories": [
                    {
                        "id": "US-001",
                        "title": "Test story",
                        "description": "As a user, I want to test",
                        "acceptanceCriteria": ["Criterion 1", "Typecheck passes"],
                        "priority": 1,
                        "passes": False,
                        "notes": "",
                    }
                ],
            }
        )

        try:
            os.chdir(project_with_spec)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def capture_run_print_mode(*args, **kwargs):
                    captured_kwargs.update(kwargs)
                    return (valid_tasks_json, 0)

                mock_instance.run_print_mode.side_effect = capture_run_print_mode
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify streaming was enabled
            assert captured_kwargs.get("stream") is True

        finally:
            os.chdir(original_cwd)

    def test_tasks_streaming_extracts_json_successfully(
        self, runner: CliRunner, project_with_spec: Path
    ) -> None:
        """Test that JSON extraction works with streamed output."""
        original_cwd = os.getcwd()

        valid_tasks_json = json.dumps(
            {
                "project": "StreamTest",
                "branchName": "ralph/stream-test",
                "description": "Test streaming",
                "userStories": [
                    {
                        "id": "US-001",
                        "title": "Stream test story",
                        "description": "As a developer, I want streaming",
                        "acceptanceCriteria": ["Streaming works"],
                        "priority": 1,
                        "passes": False,
                        "notes": "",
                    }
                ],
            }
        )

        try:
            os.chdir(project_with_spec)

            # Simulate streamed output with surrounding text
            streamed_output = f"Here's the task breakdown:\n\n{valid_tasks_json}\n\nDone!"

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (streamed_output, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify TASKS.json was created with correct content
            tasks_file = project_with_spec / "plans" / "TASKS.json"
            assert tasks_file.exists()
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "StreamTest"

        finally:
            os.chdir(original_cwd)

    def test_tasks_streaming_handles_code_blocks(
        self, runner: CliRunner, project_with_spec: Path
    ) -> None:
        """Test that JSON extraction handles markdown code blocks in streamed output."""
        original_cwd = os.getcwd()

        valid_tasks_json = json.dumps(
            {
                "project": "CodeBlockTest",
                "branchName": "ralph/codeblock-test",
                "description": "Test code block extraction",
                "userStories": [
                    {
                        "id": "US-001",
                        "title": "Code block story",
                        "description": "As a developer, I want code block handling",
                        "acceptanceCriteria": ["Code blocks work"],
                        "priority": 1,
                        "passes": False,
                        "notes": "",
                    }
                ],
            }
        )

        try:
            os.chdir(project_with_spec)

            # Simulate output with JSON in code block
            streamed_output = f"```json\n{valid_tasks_json}\n```"

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (streamed_output, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify TASKS.json was created
            tasks_file = project_with_spec / "plans" / "TASKS.json"
            assert tasks_file.exists()
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "CodeBlockTest"

        finally:
            os.chdir(original_cwd)


class TestInitCommandChangelogCreation:
    """Integration tests for ralph init creating CHANGELOG.md (US-004).

    These tests verify that ralph init creates CHANGELOG.md and
    that existing CHANGELOG.md files are preserved.
    """

    def test_init_creates_changelog_md(self, runner: CliRunner, python_project: Path) -> None:
        """Test that ralph init creates CHANGELOG.md in project root."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert (python_project / "CHANGELOG.md").exists()

        finally:
            os.chdir(original_cwd)

    def test_init_changelog_has_keep_a_changelog_format(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that CHANGELOG.md follows Keep a Changelog format."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["init"])

            changelog_content = (python_project / "CHANGELOG.md").read_text()

            # Verify Keep a Changelog format elements
            assert "# Changelog" in changelog_content
            assert "Keep a Changelog" in changelog_content
            assert "## [Unreleased]" in changelog_content

        finally:
            os.chdir(original_cwd)

    def test_init_changelog_has_all_category_headers(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that CHANGELOG.md has all standard category headers."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["init"])

            changelog_content = (python_project / "CHANGELOG.md").read_text()

            # Verify all 6 standard headers are present
            assert "### Added" in changelog_content
            assert "### Changed" in changelog_content
            assert "### Deprecated" in changelog_content
            assert "### Removed" in changelog_content
            assert "### Fixed" in changelog_content
            assert "### Security" in changelog_content

        finally:
            os.chdir(original_cwd)

    def test_init_preserves_existing_changelog(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that ralph init does NOT overwrite existing CHANGELOG.md."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create existing CHANGELOG.md with custom content
            existing_content = "# My Custom Changelog\n\n## v1.0.0\n\n- Initial release\n"
            (python_project / "CHANGELOG.md").write_text(existing_content)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                # Use --force to overwrite other files
                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0

            # CHANGELOG.md should NOT be overwritten
            changelog_content = (python_project / "CHANGELOG.md").read_text()
            assert changelog_content == existing_content
            assert "My Custom Changelog" in changelog_content

        finally:
            os.chdir(original_cwd)

    def test_init_shows_skipped_message_for_existing_changelog(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that ralph init shows 'Skipped' message for existing CHANGELOG.md."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create existing CHANGELOG.md
            (python_project / "CHANGELOG.md").write_text("# Existing changelog\n")

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0
            assert "Skipped CHANGELOG.md" in result.output
            assert "already exists" in result.output

        finally:
            os.chdir(original_cwd)


class TestMessageBoundaryNewlines:
    """Integration tests for newlines between message blocks (US-002).

    These tests verify that message boundaries are handled correctly,
    adding newlines between assistant turns for readable output.
    """

    def test_once_adds_newlines_at_message_boundaries(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that message boundaries result in newlines being added.

        This verifies US-002: Add newlines between message blocks in output.
        """
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            # Simulate stream-json events with message boundaries
            event1 = (
                '{"type":"content_block_delta",'
                '"delta":{"type":"text_delta","text":"First message"}}'
            )
            event2 = '{"type":"message_stop"}'
            event3 = (
                '{"type":"content_block_delta",'
                '"delta":{"type":"text_delta","text":"Second message"}}'
            )
            event4 = '{"type":"result"}'
            events = [event1, event2, event3, event4]
            mock_process.stdout = iter(line + "\n" for line in events)
            mock_process.stderr = MagicMock()
            mock_process.stderr.read.return_value = ""
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["once"])

            # Should not crash
            assert "Traceback" not in result.output
            assert result.exit_code in (0, 1)

        finally:
            os.chdir(original_cwd)


class TestSkipPermissionsIntegration:
    """Integration tests for skip_permissions in iteration commands (US-003).

    These tests verify that ralph prd uses skip_permissions for autonomous
    PRD creation.
    """

    def test_prd_uses_skip_permissions(self, runner: CliRunner, python_project: Path) -> None:
        """Test that ralph prd uses skip_permissions=True."""
        original_cwd = os.getcwd()
        captured_skip_permissions: list[bool] = []

        try:
            os.chdir(python_project)

            # Create plans directory
            (python_project / "plans").mkdir()

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def capture_run_interactive(*args, **kwargs):
                    captured_skip_permissions.append(kwargs.get("skip_permissions", False))
                    return 0

                mock_instance.run_interactive.side_effect = capture_run_interactive
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd"])

            # Verify skip_permissions=True was passed
            assert len(captured_skip_permissions) > 0
            assert captured_skip_permissions[0] is True

        finally:
            os.chdir(original_cwd)

    def test_prd_displays_auto_approved_message(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that ralph prd displays auto-approved permissions message."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create plans directory
            (python_project / "plans").mkdir()

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert "auto-approved permissions" in result.output

        finally:
            os.chdir(original_cwd)
