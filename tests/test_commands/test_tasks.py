"""Tests for ralph tasks command."""

import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.tasks import (
    PROGRESS_TEMPLATE,
    _archive_progress_file,
    _build_prompt_from_skill,
    _extract_json,
    _has_meaningful_content,
    _is_valid_json,
)
from ralph.services import ClaudeError, SkillNotFoundError
from tests.conftest import normalize_paths


@pytest.fixture
def initialized_project_with_spec_and_skill(temp_project: Path) -> Path:
    """Create a temporary project with plans/ directory, SPEC.md, and ralph-tasks skill.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the initialized project directory.
    """
    plans_dir = temp_project / "plans"
    plans_dir.mkdir()

    spec_file = plans_dir / "SPEC.md"
    spec_file.write_text("# Feature Spec\n\nThis is a test specification.")

    # Create skills directory with ralph-tasks skill
    skill_dir = temp_project / "skills" / "ralph-tasks"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        """---
name: ralph-tasks
description: Test tasks skill
---

# Ralph Tasks Skill

You are converting a PRD into TASKS.json user stories.

## Output Schema

Your output MUST be valid JSON matching this exact schema.

## Story Sizing Guidelines

A good user story should be completable in a single iteration.

## Typecheck passes

Always include "Typecheck passes" in acceptance criteria.
"""
    )
    return temp_project


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
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks displays informational message."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert "Converting Spec to Tasks" in result.output
            assert "plans/SPEC.md" in normalize_paths(result.output)
        finally:
            os.chdir(original_cwd)

    def test_tasks_launches_claude_in_print_mode_with_streaming(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks launches Claude Code in print mode with streaming enabled."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md"])

            # Verify ClaudeService was called correctly
            mock_claude.assert_called_once()
            mock_instance.run_print_mode.assert_called_once()

            # Verify stream=True was passed (US-008: Enable streaming for ralph tasks)
            call_kwargs = mock_instance.run_print_mode.call_args.kwargs
            assert call_kwargs.get("stream") is True
        finally:
            os.chdir(original_cwd)

    def test_tasks_includes_spec_content_in_prompt(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks includes spec content in the prompt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md"])

            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]

            # Verify prompt includes spec content
            assert "test specification" in prompt
            assert "TASKS.json" in normalize_paths(prompt)
        finally:
            os.chdir(original_cwd)

    def test_tasks_validates_claude_output(
        self, runner: CliRunner, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that tasks validates Claude output against Pydantic model."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

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
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks saves valid output to TASKS.json."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify file was created
            tasks_file = initialized_project_with_spec_and_skill / "plans" / "TASKS.json"
            assert tasks_file.exists()

            # Verify content is valid JSON
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "TestProject"
            assert len(content["userStories"]) == 1
        finally:
            os.chdir(original_cwd)

    def test_tasks_shows_success_message_with_story_count(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks shows success message with story count."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            assert "1 user stories" in result.output or "1 user stor" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_nonzero_exit_code(
        self, runner: CliRunner, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that tasks handles non-zero exit code from Claude."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Error output", 1)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "exited with code" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_claude_error(
        self, runner: CliRunner, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that tasks handles ClaudeError gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

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
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks notes when TASKS.json already exists."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Create existing TASKS.json
            tasks_path = initialized_project_with_spec_and_skill / "plans" / "TASKS.json"
            tasks_path.write_text("{}")

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert "already exists" in result.output
            assert "overwritten" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_with_custom_output_path(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks accepts custom output path."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            custom_output = "plans/CUSTOM_TASKS.json"

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md", "--output", custom_output])

            assert result.exit_code == 0
            assert normalize_paths(custom_output) in normalize_paths(result.output)

            # Verify file was created at custom path
            tasks_file = initialized_project_with_spec_and_skill / custom_output
            assert tasks_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_tasks_with_verbose_flag(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks passes verbose flag to ClaudeService."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md", "--verbose"])

            # Verify ClaudeService was created with verbose=True
            call_kwargs = mock_claude.call_args.kwargs
            assert call_kwargs.get("verbose") is True
        finally:
            os.chdir(original_cwd)

    def test_tasks_with_branch_name_flag(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks passes branch name to prompt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md", "--branch", "ralph/custom-branch"])

            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]

            # Verify branch name is in the prompt
            assert "ralph/custom-branch" in prompt
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_no_json_in_output(
        self, runner: CliRunner, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that tasks handles Claude output with no valid JSON."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Just some text without JSON", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "Could not extract valid JSON" in result.output
        finally:
            os.chdir(original_cwd)

    def test_tasks_handles_skill_not_found(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that tasks handles missing skill gracefully."""
        original_cwd = os.getcwd()
        try:
            # Create only plans dir with SPEC.md, no skills dir
            plans_dir = temp_project / "plans"
            plans_dir.mkdir()
            spec_file = plans_dir / "SPEC.md"
            spec_file.write_text("# Test Spec\n\nSome content.")
            os.chdir(temp_project)

            result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 1
            assert "Skill not found" in result.output
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


class TestBuildPromptFromSkill:
    """Tests for the _build_prompt_from_skill helper function."""

    def test_prompt_includes_spec_content(
        self, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that prompt includes the spec content."""
        spec_content = "# My Feature\n\nThis is the feature description."
        prompt = _build_prompt_from_skill(initialized_project_with_spec_and_skill, spec_content)

        assert spec_content in prompt

    def test_prompt_loads_skill_content(
        self, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that prompt loads content from skill file."""
        spec_content = "Test spec"
        prompt = _build_prompt_from_skill(initialized_project_with_spec_and_skill, spec_content)

        # Skill content should be in the prompt
        assert "Ralph Tasks Skill" in prompt
        assert "TASKS.json" in prompt
        assert "Story Sizing Guidelines" in prompt

    def test_prompt_includes_context_section(
        self, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that prompt includes context section."""
        spec_content = "Test spec"
        prompt = _build_prompt_from_skill(initialized_project_with_spec_and_skill, spec_content)

        assert "Context for This Session" in prompt
        assert "Specification content:" in prompt

    def test_prompt_with_custom_branch_name(
        self, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that prompt includes custom branch name when provided."""
        prompt = _build_prompt_from_skill(
            initialized_project_with_spec_and_skill,
            "Test spec",
            branch_name="ralph/custom-feature",
        )

        assert "ralph/custom-feature" in prompt

    def test_prompt_without_branch_name(
        self, initialized_project_with_spec_and_skill: Path
    ) -> None:
        """Test that prompt includes branch derivation instruction when no branch provided."""
        prompt = _build_prompt_from_skill(initialized_project_with_spec_and_skill, "Test spec")

        assert "Derive" in prompt

    def test_prompt_asks_for_json_only(self, initialized_project_with_spec_and_skill: Path) -> None:
        """Test that prompt explicitly asks for JSON only output."""
        prompt = _build_prompt_from_skill(initialized_project_with_spec_and_skill, "Test spec")

        # The context section should ask for JSON output
        assert "JSON only" in prompt

    def test_raises_when_skill_not_found(self, temp_project: Path) -> None:
        """Test that raises SkillNotFoundError when skill is missing."""
        with pytest.raises(SkillNotFoundError):
            _build_prompt_from_skill(temp_project, "Test spec")


class TestHasMeaningfulContent:
    """Tests for the _has_meaningful_content helper function."""

    def test_returns_false_for_empty_string(self) -> None:
        """Test that empty content returns False."""
        assert not _has_meaningful_content("")

    def test_returns_false_for_whitespace_only(self) -> None:
        """Test that whitespace-only content returns False."""
        assert not _has_meaningful_content("   \n\n   \t  ")

    def test_returns_false_for_template_only(self) -> None:
        """Test that template-only content returns False."""
        assert not _has_meaningful_content(PROGRESS_TEMPLATE)

    def test_returns_true_for_iteration_section(self) -> None:
        """Test that content with ## Iteration marker returns True."""
        content = PROGRESS_TEMPLATE + "\n## Iteration 1\nSome content here"
        assert _has_meaningful_content(content)

    def test_returns_true_for_story_marker(self) -> None:
        """Test that content with ### Story: marker returns True."""
        content = "# Progress Log\n\n### Story: US-001\n\nCompleted the task."
        assert _has_meaningful_content(content)

    def test_returns_true_for_status_marker(self) -> None:
        """Test that content with **Status:** marker returns True."""
        content = "# Progress Log\n\n**Status:** Completed\n"
        assert _has_meaningful_content(content)

    def test_returns_true_for_completed_marker(self) -> None:
        """Test that content with **Completed:** marker returns True."""
        content = "# Progress\n\n**Completed:** US-001 - Fix bug\n"
        assert _has_meaningful_content(content)

    def test_returns_true_for_what_was_implemented_section(self) -> None:
        """Test that content with ### What was implemented marker returns True."""
        content = """# Ralph Progress Log

## 2026-01-20 - US-001

### What was implemented
- Added new feature
"""
        assert _has_meaningful_content(content)

    def test_returns_true_for_tests_written_section(self) -> None:
        """Test that content with ### Tests written marker returns True."""
        content = """# Ralph Progress Log

## 2026-01-20 - US-001

### Tests written
- test_new_feature
"""
        assert _has_meaningful_content(content)

    def test_returns_true_for_files_changed_section(self) -> None:
        """Test that content with ### Files changed marker returns True."""
        content = """# Ralph Progress Log

### Files changed
- src/main.py
"""
        assert _has_meaningful_content(content)

    def test_returns_true_for_learnings_section(self) -> None:
        """Test that content with ### Learnings marker returns True."""
        content = """# Ralph Progress Log

### Learnings for future iterations
- Important pattern discovered
"""
        assert _has_meaningful_content(content)

    def test_returns_false_for_similar_but_not_matching_text(self) -> None:
        """Test that similar but non-matching text returns False."""
        content = "# Progress\n\nIteration notes\nStory details\nStatus update"
        assert not _has_meaningful_content(content)

    def test_handles_real_progress_file_from_codebase(self) -> None:
        """Test with realistic progress file content similar to actual usage."""
        content = """# Ralph Progress Log

## Codebase Patterns

- Use `create_console()` from `ralph.utils.console`

---

## Log

(Iteration entries will be appended below)

---

## 2026-01-20 - US-001

**Story:** Windows encoding detection for Rich console

### What was implemented
- Created `create_console()` function in `src/ralph/utils/console.py`

### Tests written
- `TestCreateConsole` class with 10 test cases

### Files changed
- `src/ralph/utils/console.py`
- `tests/test_utils/test_console.py`

### Learnings for future iterations
- Rich Console's `legacy_windows` parameter disables Unicode characters

---
"""
        assert _has_meaningful_content(content)

    def test_returns_false_for_modified_template_without_iterations(self) -> None:
        """Test that modified template without iterations returns False."""
        # Template with patterns section filled in but no iterations
        content = """# Ralph Progress Log

## Codebase Patterns

- Use `create_console()` from `ralph.utils.console`
- Important pattern here

---

## Log

(Iteration entries will be appended below)

---
"""
        assert not _has_meaningful_content(content)


class TestArchiveProgressFile:
    """Tests for the _archive_progress_file helper function."""

    def test_returns_none_if_progress_does_not_exist(self, temp_project: Path) -> None:
        """Test that function returns None if PROGRESS.txt doesn't exist."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()

        result = _archive_progress_file(temp_project)

        assert result is None

    def test_returns_none_if_progress_is_empty(self, temp_project: Path) -> None:
        """Test that function returns None if PROGRESS.txt is empty."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("")

        result = _archive_progress_file(temp_project)

        assert result is None

    def test_returns_none_if_progress_only_whitespace(self, temp_project: Path) -> None:
        """Test that function returns None if PROGRESS.txt contains only whitespace."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text("   \n\n   ")

        result = _archive_progress_file(temp_project)

        assert result is None

    def test_returns_none_if_progress_is_template_only(self, temp_project: Path) -> None:
        """Test that function returns None if PROGRESS.txt contains only template content."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        (plans_dir / "PROGRESS.txt").write_text(PROGRESS_TEMPLATE)

        result = _archive_progress_file(temp_project)

        assert result is None
        # Verify no archive was created
        archived_files = list(plans_dir.glob("PROGRESS.*.txt"))
        assert len(archived_files) == 0

    def test_returns_none_if_progress_is_modified_template_without_iterations(
        self, temp_project: Path
    ) -> None:
        """Test function returns None for modified template without iteration content."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        # Template with patterns filled in but no iteration entries
        modified_template = """# Ralph Progress Log

## Codebase Patterns

- Use `create_console()` from `ralph.utils.console`
- Important pattern here

---

## Log

(Iteration entries will be appended below)

---
"""
        (plans_dir / "PROGRESS.txt").write_text(modified_template)

        result = _archive_progress_file(temp_project)

        assert result is None

    def test_archives_progress_with_iteration_content(self, temp_project: Path) -> None:
        """Test that PROGRESS.txt with iteration content is archived correctly."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        original_content = """# Ralph Progress Log

## Codebase Patterns

---

## Log

---

## 2026-01-20 - US-001

**Story:** Implement feature

### What was implemented
- Added new feature

### Tests written
- test_new_feature

### Files changed
- src/main.py

### Learnings for future iterations
- Important discovery
"""
        (plans_dir / "PROGRESS.txt").write_text(original_content)

        result = _archive_progress_file(temp_project)

        assert result is not None
        assert result.exists()
        assert result.read_text() == original_content

    def test_archives_existing_progress_file(self, temp_project: Path) -> None:
        """Test that existing PROGRESS.txt with meaningful content is archived correctly."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        # Content with iteration marker
        original_content = "# Progress Log\n\n### What was implemented\n- Completed story"
        (plans_dir / "PROGRESS.txt").write_text(original_content)

        result = _archive_progress_file(temp_project)

        assert result is not None
        assert result.exists()
        assert result.read_text() == original_content

    def test_archive_uses_correct_timestamp_format(self, temp_project: Path) -> None:
        """Test that archive filename uses YYYYMMDD_HHMMSS format."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        # Use meaningful content to trigger archival
        (plans_dir / "PROGRESS.txt").write_text("# Progress\n\n### What was implemented\n- Work")

        result = _archive_progress_file(temp_project)

        assert result is not None
        # Pattern: PROGRESS.YYYYMMDD_HHMMSS.txt
        pattern = r"PROGRESS\.\d{8}_\d{6}\.txt"
        assert re.match(pattern, result.name)

    def test_creates_fresh_progress_with_template(self, temp_project: Path) -> None:
        """Test that fresh PROGRESS.txt is created with header template."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        # Use meaningful content to trigger archival
        (plans_dir / "PROGRESS.txt").write_text("# Old Progress\n\n### What was implemented\n- X")

        _archive_progress_file(temp_project)

        new_progress = plans_dir / "PROGRESS.txt"
        assert new_progress.exists()
        assert new_progress.read_text() == PROGRESS_TEMPLATE

    def test_fresh_progress_has_expected_sections(self, temp_project: Path) -> None:
        """Test that fresh PROGRESS.txt has expected sections."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        # Use meaningful content to trigger archival
        (plans_dir / "PROGRESS.txt").write_text("# Old Content\n\n### What was implemented\n- Y")

        _archive_progress_file(temp_project)

        content = (plans_dir / "PROGRESS.txt").read_text()
        assert "# Ralph Progress Log" in content
        assert "## Codebase Patterns" in content
        assert "## Log" in content

    def test_does_not_archive_template_preserves_original_file(self, temp_project: Path) -> None:
        """Test that when template-only, original file is preserved unchanged."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        original_content = PROGRESS_TEMPLATE
        progress_file = plans_dir / "PROGRESS.txt"
        progress_file.write_text(original_content)

        result = _archive_progress_file(temp_project)

        assert result is None
        # Original file should be unchanged
        assert progress_file.read_text() == original_content


class TestTasksCommandProgressArchival:
    """Integration tests for PROGRESS.txt archival in tasks command."""

    def test_tasks_archives_progress_file_with_meaningful_content(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks command archives PROGRESS.txt with iteration content."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Create existing PROGRESS.txt with meaningful iteration content
            plans_dir = initialized_project_with_spec_and_skill / "plans"
            progress_file = plans_dir / "PROGRESS.txt"
            original_content = """# Progress Log

### What was implemented
- Completed implementation
"""
            progress_file.write_text(original_content)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Check archive was created
            archived_files = list(plans_dir.glob("PROGRESS.*.txt"))
            assert len(archived_files) == 1
            assert archived_files[0].read_text() == original_content

        finally:
            os.chdir(original_cwd)

    def test_tasks_displays_archive_message(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks command displays archive message."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Create existing PROGRESS.txt with meaningful content
            plans_dir = initialized_project_with_spec_and_skill / "plans"
            (plans_dir / "PROGRESS.txt").write_text("# Progress\n\n### What was implemented\n- X")

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            assert "Archived previous progress to" in result.output
            assert "PROGRESS." in result.output

        finally:
            os.chdir(original_cwd)

    def test_tasks_creates_fresh_progress_file(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks command creates fresh PROGRESS.txt after archiving."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Create existing PROGRESS.txt with meaningful content
            plans_dir = initialized_project_with_spec_and_skill / "plans"
            (plans_dir / "PROGRESS.txt").write_text("# Old\n\n### What was implemented\n- Old")

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # New PROGRESS.txt should have fresh template
            new_progress = plans_dir / "PROGRESS.txt"
            assert new_progress.exists()
            assert "# Ralph Progress Log" in new_progress.read_text()
            assert "## Codebase Patterns" in new_progress.read_text()

        finally:
            os.chdir(original_cwd)

    def test_tasks_does_not_archive_empty_progress(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks command does not archive empty PROGRESS.txt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Create empty PROGRESS.txt
            plans_dir = initialized_project_with_spec_and_skill / "plans"
            (plans_dir / "PROGRESS.txt").write_text("")

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            assert "Archived previous progress" not in result.output

            # No archive file should be created
            archived_files = list(plans_dir.glob("PROGRESS.*.txt"))
            assert len(archived_files) == 0

        finally:
            os.chdir(original_cwd)

    def test_tasks_does_not_archive_nonexistent_progress(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks command does not archive if PROGRESS.txt doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            assert "Archived previous progress" not in result.output

        finally:
            os.chdir(original_cwd)

    def test_tasks_does_not_archive_template_only_progress(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks command does not archive template-only PROGRESS.txt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Create PROGRESS.txt with only template content
            plans_dir = initialized_project_with_spec_and_skill / "plans"
            (plans_dir / "PROGRESS.txt").write_text(PROGRESS_TEMPLATE)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            assert "Archived previous progress" not in result.output

            # No archive file should be created
            archived_files = list(plans_dir.glob("PROGRESS.*.txt"))
            assert len(archived_files) == 0

        finally:
            os.chdir(original_cwd)


class TestTasksSkipPermissions:
    """Tests for skip_permissions functionality in tasks command."""

    def test_tasks_passes_skip_permissions_true(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that tasks calls run_print_mode with skip_permissions=True."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["tasks", "plans/SPEC.md"])

            # Verify run_print_mode was called with skip_permissions=True
            call_kwargs = mock_instance.run_print_mode.call_args.kwargs
            assert call_kwargs.get("skip_permissions") is True
        finally:
            os.chdir(original_cwd)


class TestTasksCommandStreaming:
    """Tests for streaming behavior in ralph tasks command (US-008)."""

    def test_tasks_streaming_extracts_json_from_text_output(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that JSON extraction works when streaming is enabled.

        When streaming is enabled, the ClaudeService returns extracted text content
        (not raw JSON events). The _extract_json function should still be able to
        extract the TASKS.json from this output.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Simulate streamed output - the ClaudeService extracts text from events
            # and returns it as plain text
            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify file was created with valid content
            tasks_file = initialized_project_with_spec_and_skill / "plans" / "TASKS.json"
            assert tasks_file.exists()
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "TestProject"

        finally:
            os.chdir(original_cwd)

    def test_tasks_streaming_handles_json_in_code_block(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that JSON extraction handles code blocks in streamed output.

        Claude may output JSON wrapped in markdown code blocks even when streaming.
        The extraction should handle this case.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Simulate streamed output with JSON in a code block
            streamed_output = f"Here's the TASKS.json:\n```json\n{valid_tasks_json_str}\n```"

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (streamed_output, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify file was created with valid content
            tasks_file = initialized_project_with_spec_and_skill / "plans" / "TASKS.json"
            assert tasks_file.exists()
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "TestProject"

        finally:
            os.chdir(original_cwd)

    def test_tasks_streaming_handles_text_with_embedded_json(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that JSON extraction handles JSON embedded in text.

        Claude may output explanatory text before/after the JSON when streaming.
        The extraction should find and extract the JSON.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            # Simulate streamed output with text before and after JSON
            streamed_output = (
                "I've analyzed the specification and created the following "
                f"task breakdown:\n\n{valid_tasks_json_str}\n\n"
                "This covers all the requirements from your PRD."
            )

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (streamed_output, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0

            # Verify file was created with valid content
            tasks_file = initialized_project_with_spec_and_skill / "plans" / "TASKS.json"
            assert tasks_file.exists()
            content = json.loads(tasks_file.read_text())
            assert content["project"] == "TestProject"

        finally:
            os.chdir(original_cwd)

    def test_tasks_streaming_shows_progress_during_generation(
        self,
        runner: CliRunner,
        initialized_project_with_spec_and_skill: Path,
        valid_tasks_json_str: str,
    ) -> None:
        """Test that streaming output message is displayed.

        When streaming is enabled, the user should see a message indicating
        that Claude is generating tasks.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_spec_and_skill)

            with patch("ralph.commands.tasks.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (valid_tasks_json_str, 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

            assert result.exit_code == 0
            # Verify informational message is shown before generation
            assert "Running Claude to generate tasks" in result.output

        finally:
            os.chdir(original_cwd)
