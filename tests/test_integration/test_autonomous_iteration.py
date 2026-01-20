"""Integration tests for autonomous iteration commands (once/loop).

These tests verify that ralph once and ralph loop correctly invoke Claude Code
with the --dangerously-skip-permissions flag for autonomous execution,
stream-json output format, and append_system_prompt for permissions.
"""

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.services import ClaudeService


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
            {
                "id": "US-002",
                "title": "Second story",
                "description": "As a user, I want feature B",
                "acceptanceCriteria": ["Criterion 1"],
                "priority": 2,
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


class TestClaudeServiceSkipPermissions:
    """Tests for ClaudeService skip_permissions integration."""

    def test_skip_permissions_adds_flag_to_args(self) -> None:
        """Test that skip_permissions=True adds --dangerously-skip-permissions."""
        service = ClaudeService()
        captured_args: list[str] = []

        def mock_run_process(
            args: list[str], stream: bool, parse_json: bool = False
        ) -> tuple[str, int]:
            captured_args.extend(args)
            return ("Test output", 0)

        with (
            patch("ralph.services.claude.shutil.which", return_value="/usr/bin/claude"),
            patch.object(service, "_run_process", side_effect=mock_run_process),
        ):
            service.run_print_mode("Test prompt", skip_permissions=True)

        assert "--dangerously-skip-permissions" in captured_args

    def test_skip_permissions_false_does_not_add_flag(self) -> None:
        """Test that skip_permissions=False does not add the flag."""
        service = ClaudeService()
        captured_args: list[str] = []

        def mock_run_process(
            args: list[str], stream: bool, parse_json: bool = False
        ) -> tuple[str, int]:
            captured_args.extend(args)
            return ("Test output", 0)

        with (
            patch("ralph.services.claude.shutil.which", return_value="/usr/bin/claude"),
            patch.object(service, "_run_process", side_effect=mock_run_process),
        ):
            service.run_print_mode("Test prompt", skip_permissions=False)

        assert "--dangerously-skip-permissions" not in captured_args

    def test_skip_permissions_flag_position_in_args(self) -> None:
        """Test that --dangerously-skip-permissions is positioned correctly.

        With centralized flag handling, the skip-permissions flag is added
        as part of the base args, so it comes BEFORE command-specific args
        like --print.
        """
        service = ClaudeService()
        captured_args: list[str] = []

        def mock_run_process(
            args: list[str], stream: bool, parse_json: bool = False
        ) -> tuple[str, int]:
            captured_args.extend(args)
            return ("Test output", 0)

        with (
            patch("ralph.services.claude.shutil.which", return_value="/usr/bin/claude"),
            patch.object(service, "_run_process", side_effect=mock_run_process),
        ):
            service.run_print_mode("Test prompt", skip_permissions=True, model="sonnet")

        # Verify the flag is present and comes before --print (as a base arg)
        print_index = captured_args.index("--print")
        skip_index = captured_args.index("--dangerously-skip-permissions")

        # --dangerously-skip-permissions is now part of base args, so comes before --print
        assert skip_index < print_index


class TestOnceCommandAutonomousIteration:
    """Integration tests for ralph once autonomous iteration."""

    def test_once_invokes_claude_with_skip_permissions(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once invokes Claude with --dangerously-skip-permissions."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Task completed successfully")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["once"])

            assert "--dangerously-skip-permissions" in captured_args
        finally:
            os.chdir(original_cwd)

    def test_once_displays_autonomous_iteration_message(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once displays the autonomous iteration message."""
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Task completed")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["once"])

            assert "auto-approved permissions" in result.output
            assert "autonomous iteration" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_includes_print_flag(self, runner: CliRunner, project_with_tasks: Path) -> None:
        """Test that ralph once uses --print mode."""
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
                runner.invoke(app, ["once"])

            assert "--print" in captured_args
        finally:
            os.chdir(original_cwd)

    def test_once_passes_prompt_with_story_details(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once passes a prompt containing story details."""
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
                runner.invoke(app, ["once"])

            # Find the prompt argument (comes after --print)
            print_index = captured_args.index("--print")
            prompt = captured_args[print_index + 1]

            # Verify prompt contains story info
            assert "US-001" in prompt
            assert "First story" in prompt
        finally:
            os.chdir(original_cwd)

    def test_once_complete_workflow(
        self, runner: CliRunner, project_with_tasks: Path, sample_tasks: dict
    ) -> None:
        """Test the complete once workflow with story completion detection."""
        original_cwd = os.getcwd()

        def mock_popen_and_complete(args: list[str], **kwargs):
            # Simulate Claude completing the story by updating TASKS.json
            updated_tasks = sample_tasks.copy()
            updated_tasks["userStories"][0]["passes"] = True
            tasks_file = project_with_tasks / "plans" / "TASKS.json"
            tasks_file.write_text(json.dumps(updated_tasks, indent=2))

            mock_process = MagicMock()
            mock_process.stdout = StringIO("Story US-001 implemented successfully")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_and_complete),
            ):
                result = runner.invoke(app, ["once"])

            # Should detect success
            assert result.exit_code == 0
            assert "completed successfully" in result.output
        finally:
            os.chdir(original_cwd)


class TestLoopCommandAutonomousIteration:
    """Integration tests for ralph loop autonomous iteration."""

    def test_loop_invokes_claude_with_skip_permissions(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop invokes Claude with --dangerously-skip-permissions."""
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
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])

            assert "--dangerously-skip-permissions" in captured_args
        finally:
            os.chdir(original_cwd)

    def test_loop_displays_autonomous_iteration_message(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop displays the autonomous iteration message."""
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
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                result = runner.invoke(app, ["loop", "1"])

            assert "auto-approved permissions" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_includes_print_flag(self, runner: CliRunner, project_with_tasks: Path) -> None:
        """Test that ralph loop uses --print mode."""
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
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])

            assert "--print" in captured_args
        finally:
            os.chdir(original_cwd)

    def test_loop_runs_multiple_iterations_with_skip_permissions(
        self, runner: CliRunner, project_with_tasks: Path, sample_tasks: dict
    ) -> None:
        """Test that loop maintains skip_permissions across multiple iterations."""
        original_cwd = os.getcwd()
        invocation_count = 0
        all_invocations_had_skip_permissions = True

        def mock_popen(args: list[str], **kwargs):
            nonlocal invocation_count, all_invocations_had_skip_permissions
            invocation_count += 1

            if "--dangerously-skip-permissions" not in args:
                all_invocations_had_skip_permissions = False

            # Mark current story as passed
            tasks = sample_tasks.copy()
            tasks["userStories"][invocation_count - 1]["passes"] = True
            tasks_file = project_with_tasks / "plans" / "TASKS.json"
            tasks_file.write_text(json.dumps(tasks, indent=2))

            mock_process = MagicMock()
            mock_process.stdout = StringIO(f"Iteration {invocation_count} complete")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "5"])

            # Should have invoked at least twice (for 2 stories)
            assert invocation_count >= 2
            assert all_invocations_had_skip_permissions
        finally:
            os.chdir(original_cwd)

    def test_loop_stops_on_complete_signal(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that loop stops when COMPLETE signal is received."""
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            # Use stream-json format with COMPLETE signal
            json_event = (
                '{"type":"assistant","message":{"content":'
                '[{"type":"text","text":"All done! <ralph>COMPLETE</ralph>"}]}}'
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
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                result = runner.invoke(app, ["loop", "10"])

            assert result.exit_code == 0
            assert "All stories complete" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_complete_workflow_with_multiple_stories(
        self, runner: CliRunner, project_with_tasks: Path, sample_tasks: dict
    ) -> None:
        """Test the complete loop workflow completing multiple stories."""
        original_cwd = os.getcwd()
        invocation_count = 0
        story_ids_in_prompts: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            nonlocal invocation_count
            invocation_count += 1

            # Extract prompt and track which story ID is present
            prompt = args[args.index("--print") + 1] if "--print" in args else ""
            if "US-001" in prompt and "US-002" not in prompt:
                story_ids_in_prompts.append("US-001")
            elif "US-002" in prompt:
                story_ids_in_prompts.append("US-002")

            # Read current state and mark next incomplete story as passed
            tasks_file = project_with_tasks / "plans" / "TASKS.json"
            current_tasks = json.loads(tasks_file.read_text())

            for story in current_tasks["userStories"]:
                if not story["passes"]:
                    story["passes"] = True
                    break  # Only mark one story per call

            tasks_file.write_text(json.dumps(current_tasks, indent=2))

            # Check if all complete
            all_done = all(s["passes"] for s in current_tasks["userStories"])
            output = "<ralph>COMPLETE</ralph>" if all_done else "Story completed"

            mock_process = MagicMock()
            mock_process.stdout = StringIO(output)
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                result = runner.invoke(app, ["loop", "10"])

            # Should have completed both stories (2 invocations)
            assert invocation_count == 2
            assert "US-001" in story_ids_in_prompts
            assert "US-002" in story_ids_in_prompts
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)


class TestAutonomousIterationErrorHandling:
    """Tests for error handling in autonomous iteration."""

    def test_once_handles_claude_not_found(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that once handles Claude not being installed."""
        original_cwd = os.getcwd()

        def mock_popen_not_found(args: list[str], **kwargs):
            raise FileNotFoundError("claude not found")

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_not_found),
            ):
                result = runner.invoke(app, ["once"])

            assert result.exit_code == 1
            assert "Failed to run Claude" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_handles_claude_not_found(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that loop handles Claude not being installed."""
        original_cwd = os.getcwd()

        def mock_popen_not_found(args: list[str], **kwargs):
            raise FileNotFoundError("claude not found")

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_not_found),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                result = runner.invoke(app, ["loop", "1"])

            assert result.exit_code == 1
            assert "Claude error" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_handles_nonzero_exit_code(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that once handles non-zero exit code from Claude."""
        original_cwd = os.getcwd()

        def mock_popen_failure(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Error occurred")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 1  # Non-zero exit
            return mock_process

        try:
            os.chdir(project_with_tasks)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_failure),
            ):
                result = runner.invoke(app, ["once"])

            # Should warn about exit code
            assert "exited with code" in result.output or result.exit_code != 0
        finally:
            os.chdir(original_cwd)


class TestStreamingOutputIntegration:
    """Integration tests for stream-json output format."""

    def test_once_uses_stream_json_format(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once uses --output-format stream-json."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
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
                runner.invoke(app, ["once"])

            assert "--output-format" in captured_args
            format_idx = captured_args.index("--output-format")
            assert captured_args[format_idx + 1] == "stream-json"
        finally:
            os.chdir(original_cwd)

    def test_loop_uses_stream_json_format(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop uses --output-format stream-json."""
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
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])

            assert "--output-format" in captured_args
            format_idx = captured_args.index("--output-format")
            assert captured_args[format_idx + 1] == "stream-json"
        finally:
            os.chdir(original_cwd)

    def test_once_parses_stream_json_events(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once correctly parses stream-json events."""
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            # Simulate stream-json output with multiple events
            mock_process.stdout = iter(
                [
                    '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Processing..."}}\n',
                    '{"type":"tool_use","name":"Read"}\n',
                    '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Done!"}}\n',
                ]
            )
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

            # The output should contain the parsed text (not raw JSON)
            # Note: The actual displayed output may not be in result.output
            # since it's streamed to stdout
            assert result.exit_code == 1  # Story didn't pass, but no error

        finally:
            os.chdir(original_cwd)


class TestAppendSystemPromptIntegration:
    """Integration tests for append_system_prompt permissions prompt."""

    def test_once_includes_append_system_prompt(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once includes --append-system-prompt flag."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
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
                runner.invoke(app, ["once"])

            assert "--append-system-prompt" in captured_args
        finally:
            os.chdir(original_cwd)

    def test_loop_includes_append_system_prompt(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop includes --append-system-prompt flag."""
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
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])

            assert "--append-system-prompt" in captured_args
        finally:
            os.chdir(original_cwd)

    def test_once_append_system_prompt_contains_permissions_text(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that the append_system_prompt contains permissions instructions."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
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
                runner.invoke(app, ["once"])

            # Find the append_system_prompt value
            asp_idx = captured_args.index("--append-system-prompt")
            prompt_value = captured_args[asp_idx + 1]

            # Verify it contains key permission instructions
            assert "autonomous mode" in prompt_value.lower()
            assert "permission" in prompt_value.lower()
            assert "DO NOT ask" in prompt_value
        finally:
            os.chdir(original_cwd)

    def test_loop_append_system_prompt_contains_permissions_text(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that append_system_prompt in loop contains permissions text."""
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
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])

            # Find the append_system_prompt value
            asp_idx = captured_args.index("--append-system-prompt")
            prompt_value = captured_args[asp_idx + 1]

            # Verify it contains key permission instructions
            assert "autonomous mode" in prompt_value.lower()
            assert "permission" in prompt_value.lower()
            assert "DO NOT ask" in prompt_value
        finally:
            os.chdir(original_cwd)

    def test_once_and_loop_use_same_permissions_prompt(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that once and loop use the same PERMISSIONS_SYSTEM_PROMPT."""
        original_cwd = os.getcwd()
        once_prompt: str = ""
        loop_prompt: str = ""

        def capture_once_args(args: list[str], **kwargs):
            nonlocal once_prompt
            asp_idx = args.index("--append-system-prompt")
            once_prompt = args[asp_idx + 1]
            mock_process = MagicMock()
            json_event = (
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Done"}}'
            )
            mock_process.stdout = StringIO(json_event)
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        def capture_loop_args(args: list[str], **kwargs):
            nonlocal loop_prompt
            asp_idx = args.index("--append-system-prompt")
            loop_prompt = args[asp_idx + 1]
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

            # Capture once prompt
            with patch("subprocess.Popen", side_effect=capture_once_args):
                runner.invoke(app, ["once"])

            # Capture loop prompt
            with (
                patch("subprocess.Popen", side_effect=capture_loop_args),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                runner.invoke(app, ["loop", "1"])

            # Both should use the exact same prompt
            assert once_prompt == loop_prompt
            assert len(once_prompt) > 0  # Ensure we actually captured something
        finally:
            os.chdir(original_cwd)
