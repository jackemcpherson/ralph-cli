"""Tests for ralph tasks command."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.tasks import _build_tasks_prompt, _extract_json, _is_valid_json
from ralph.services import ClaudeError


# Alias for the shared fixture (tasks tests use "initialized_project_with_spec")
@pytest.fixture
def initialized_project(initialized_project_with_spec: Path) -> Path:
    """Alias for initialized_project_with_spec fixture for backward compatibility."""
    return initialized_project_with_spec


# Alias for the shared fixture (tasks tests use "valid_tasks_json" as a string)
@pytest.fixture
def valid_tasks_json(valid_tasks_json_str: str) -> str:
    """Alias for valid_tasks_json_str fixture for backward compatibility."""
    return valid_tasks_json_str


class TestTasksCommand:
    """Tests for the tasks command."""

    def test_tasks_requires_spec_file_argument(self, runner: CliRunner) -> None:
        """Test that tasks requires a spec file argument."""
        result = runner.invoke(app, ["tasks"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "SPEC_FILE" in result.output

    def test_tasks_fails_for_nonexistent_file(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that tasks fails if spec file doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            result = runner.invoke(app, ["tasks", "nonexistent.md"])

            assert result.exit_code != 0
        finally:
            os.chdir(original_cwd)

    def test_tasks_fails_for_empty_spec_file(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that tasks fails if spec file is empty."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            # Create empty spec file
            plans_dir = temp_project / "plans"
            plans_dir.mkdir()
            spec_file = plans_dir / "SPEC.md"
            spec_file.write_text("")

            result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "empty" in result.output.lower()
        finally:
            os.chdir(original_cwd)

    def test_tasks_displays_informational_message(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks displays informational message."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert "Converting Spec to Tasks" in result.output
            assert "plans/SPEC.md" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_launches_claude_in_print_mode(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks launches Claude Code in print mode."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md"])

            # Verify ClaudeService was called correctly
            mock_claude.assert_called_once()
            mock_instance.run_print_mode.assert_called_once()

            # Verify stream=False was passed
            call_kwargs = mock_instance.run_print_mode.call_args.kwargs
            assert call_kwargs.get("stream") is False
        finally:
            os.chdir(original_cwd)

    def test_tasks_includes_spec_content_in_prompt(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks includes spec content in the prompt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md"])

            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]

            # Verify prompt includes spec content
            assert "test specification" in prompt
            assert "TASKS.json" in prompt
        finally:
            os.chdir(original_cwd)

    def test_tasks_validates_claude_output(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that tasks validates Claude output against Pydantic model."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Return invalid JSON that doesn't match the model
            invalid_json = json.dumps({"invalid": "structure"})

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (invalid_json, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "does not match" in result.output or "Validation errors" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_saves_valid_output(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks saves valid output to TASKS.json."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify file was created
            tasks_file = initialized_project / "plans" / "TASKS.json"
            assert tasks_file.exists()

            # Verify content is valid JSON
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "TestProject"
            assert len(content["userStories"]) == 1
        finally:
            os.chdir(original_cwd)

    def test_tasks_shows_success_message_with_story_count(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks shows success message with story count."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            assert "1 user stories" in result.output or "1 user stor" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_nonzero_exit_code(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that tasks handles non-zero exit code from Claude."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Error output", 1)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "exited with code" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_claude_error(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that tasks handles ClaudeError gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = ClaudeError("Claude not installed")
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "Failed to run Claude" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_notes_existing_tasks_json(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks notes when TASKS.json already exists."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create existing TASKS.json
            tasks_path = initialized_project / "plans" / "TASKS.json"
            tasks_path.write_text("{}")

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert "already exists" in result.output
            assert "overwritten" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_with_custom_output_path(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks accepts custom output path."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            custom_output = "plans/CUSTOM_TASKS.json"

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md", "--output", custom_output])

            assert result.exit_code == 0
            assert custom_output in result.output

            # Verify file was created at custom path
            tasks_file = initialized_project / custom_output
            assert tasks_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_tasks_with_verbose_flag(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks passes verbose flag to ClaudeService."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md", "--verbose"])

            # Verify ClaudeService was created with verbose=True
            call_kwargs = mock_claude.call_args.kwargs
            assert call_kwargs.get("verbose") is True
        finally:
            os.chdir(original_cwd)

    def test_tasks_with_branch_name_flag(
        self, runner: CliRunner, initialized_project: Path, valid_tasks_json: str
    ) -> None:
        """Test that tasks passes branch name to prompt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md", "--branch", "ralph/custom-branch"])

            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]

            # Verify branch name is in the prompt
            assert "ralph/custom-branch" in prompt
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_no_json_in_output(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that tasks handles Claude output with no valid JSON."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Just some text without JSON", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "Could not extract valid JSON" in result.output
        finally:
            os.chdir(original_cwd)


class TestExtractJson:
    """Tests for the _extract_json helper function."""

    def test_extract_pure_json(self) -> None:
        """Test extracting pure JSON."""
        json_text = '{"key": "value"}'
        result = _extract_json(json_text)
        assert result == json_text

    def test_extract_json_from_code_block(self) -> None:
        """Test extracting JSON from markdown code block."""
        text = 'Here is the JSON:\n```json\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_from_code_block_no_language(self) -> None:
        """Test extracting JSON from code block without language specifier."""
        text = 'Here is the JSON:\n```\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_from_surrounding_text(self) -> None:
        """Test extracting JSON from surrounding text."""
        text = 'Here is the result:\n{"key": "value"}\nDone!'
        result = _extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_complex_object(self) -> None:
        """Test extracting complex JSON object."""
        json_obj = {
            "project": "Test",
            "userStories": [{"id": "US-001", "title": "Test"}],
        }
        text = f"```json\n{json.dumps(json_obj)}\n```"
        result = _extract_json(text)
        assert result is not None
        assert json.loads(result) == json_obj

    def test_extract_json_returns_none_for_invalid(self) -> None:
        """Test that _extract_json returns None for invalid input."""
        text = "This is just plain text without any JSON"
        result = _extract_json(text)
        assert result is None

    def test_extract_json_whitespace_handling(self) -> None:
        """Test that _extract_json handles whitespace properly."""
        text = '  \n  {"key": "value"}  \n  '
        result = _extract_json(text)
        assert result == '{"key": "value"}'


class TestIsValidJson:
    """Tests for the _is_valid_json helper function."""

    def test_valid_json_object(self) -> None:
        """Test valid JSON object."""
        assert _is_valid_json('{"key": "value"}')

    def test_valid_json_array(self) -> None:
        """Test valid JSON array."""
        assert _is_valid_json("[1, 2, 3]")

    def test_invalid_json(self) -> None:
        """Test invalid JSON."""
        assert not _is_valid_json("not json")

    def test_malformed_json(self) -> None:
        """Test malformed JSON."""
        assert not _is_valid_json('{"key": "value"')


class TestBuildTasksPrompt:
    """Tests for the _build_tasks_prompt helper function."""

    def test_prompt_includes_spec_content(self) -> None:
        """Test that prompt includes the spec content."""
        spec_content = "# My Feature\n\nThis is the feature description."
        prompt = _build_tasks_prompt(spec_content)

        assert spec_content in prompt

    def test_prompt_includes_json_schema(self) -> None:
        """Test that prompt includes JSON schema guidance."""
        prompt = _build_tasks_prompt("Test spec")

        assert "project" in prompt
        assert "branchName" in prompt
        assert "userStories" in prompt
        assert "acceptanceCriteria" in prompt

    def test_prompt_includes_guidelines(self) -> None:
        """Test that prompt includes story creation guidelines."""
        prompt = _build_tasks_prompt("Test spec")

        assert "atomic" in prompt.lower() or "implementable" in prompt.lower()
        assert "Typecheck passes" in prompt

    def test_prompt_with_custom_branch_name(self) -> None:
        """Test that prompt includes custom branch name when provided."""
        prompt = _build_tasks_prompt("Test spec", branch_name="ralph/custom-feature")

        assert "ralph/custom-feature" in prompt

    def test_prompt_without_branch_name(self) -> None:
        """Test that prompt includes branch derivation instruction when no branch provided."""
        prompt = _build_tasks_prompt("Test spec")

        assert "Derive the branch name" in prompt

    def test_prompt_asks_for_json_only(self) -> None:
        """Test that prompt explicitly asks for JSON only output."""
        prompt = _build_tasks_prompt("Test spec")

        assert "ONLY valid JSON" in prompt or "JSON only" in prompt
