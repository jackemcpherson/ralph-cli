"""Tests for already-implemented story detection in ralph tasks command.

Tests for US-012: Add unit tests for already-implemented story detection.
Verifies that the codebase context is included in the prompt, that stories
with passes: true are counted and logged correctly, and that normal
operation works when no stories are detected.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from ralph.models import TasksFile

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def working_directory(path: Path) -> Iterator[Path]:
    """Temporarily change working directory."""
    original = os.getcwd()
    try:
        os.chdir(path)
        yield path
    finally:
        os.chdir(original)


def _make_tasks_file(stories: list[dict[str, object]]) -> TasksFile:
    """Build a TasksFile from a list of story dicts."""
    return TasksFile(
        project="TestProject",
        branch_name="ralph/test",
        description="Test",
        user_stories=stories,
    )


def _make_story(
    story_id: str,
    title: str,
    *,
    passes: bool = False,
    notes: str = "",
) -> dict[str, object]:
    """Build a minimal story dict."""
    return {
        "id": story_id,
        "title": title,
        "description": "Test description",
        "acceptanceCriteria": ["Criterion 1"],
        "priority": 1,
        "passes": passes,
        "notes": notes,
    }


def _tasks_json_payload(stories: list[dict[str, object]]) -> str:
    """Serialise stories to a TASKS.json-shaped JSON string."""
    return json.dumps(
        {
            "project": "TestProject",
            "branchName": "ralph/test",
            "description": "Test",
            "userStories": stories,
        }
    )


# ---------------------------------------------------------------------------
# AC-1: Codebase summary is included in the prompt when generating tasks
# ---------------------------------------------------------------------------


class TestCodebaseSummaryInPrompt:
    """Verify codebase context appears in the prompt sent to Claude."""

    def test_prompt_contains_existing_codebase_summary_heading(self, tmp_path: Path) -> None:
        """The prompt must include the Existing Codebase Summary heading."""
        from ralph.commands.tasks import _build_prompt_from_skill

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "acme"\n')

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("Some spec")

        assert "## Existing Codebase Summary" in prompt

    def test_prompt_contains_already_implemented_detection_section(self, tmp_path: Path) -> None:
        """The prompt must include instructions for already-implemented detection."""
        from ralph.commands.tasks import _build_prompt_from_skill

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("Some spec")

        assert "## Instructions for Already-Implemented Detection" in prompt
        assert "passes: true" in prompt

    def test_prompt_includes_file_tree_of_project(self, tmp_path: Path) -> None:
        """The prompt must contain the project's file tree."""
        from ralph.commands.tasks import _build_prompt_from_skill

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "core.py").write_text("")

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("spec")

        assert "### File Tree" in prompt
        assert "core.py" in prompt

    def test_prompt_includes_key_file_contents(self, tmp_path: Path) -> None:
        """The prompt must include key file content like pyproject.toml."""
        from ralph.commands.tasks import _build_prompt_from_skill

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "acme"\n')
        (tmp_path / "README.md").write_text("# Acme\n\nA cool project.")

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("spec")

        assert "### pyproject.toml" in prompt
        assert 'name = "acme"' in prompt
        assert "### README.md" in prompt

    def test_tasks_command_sends_codebase_context_to_claude(self, tmp_path: Path) -> None:
        """End-to-end: tasks command passes codebase context to Claude."""
        from typer.testing import CliRunner

        from ralph.cli import app

        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "SPEC.md").write_text("# Spec\n\nBuild something.")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main(): pass\n")

        valid_json = _tasks_json_payload([_make_story("US-001", "Build something", passes=False)])
        captured_prompt: list[str] = []

        mock_instance = MagicMock()

        def capture_run(*args: object, **_kw: object) -> tuple[str, int]:
            if args:
                captured_prompt.append(str(args[0]))
            return (valid_json, 0)

        mock_instance.run_print_mode.side_effect = capture_run

        runner = CliRunner()
        with working_directory(tmp_path):
            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

        assert result.exit_code == 0
        assert len(captured_prompt) == 1
        assert "Existing Codebase Summary" in captured_prompt[0]
        assert "app.py" in captured_prompt[0]
        assert "Already-Implemented Detection" in captured_prompt[0]


# ---------------------------------------------------------------------------
# AC-2: Stories with passes: true are counted and logged correctly
# ---------------------------------------------------------------------------


class TestAlreadyImplementedCounting:
    """Verify correct counting and logging of already-implemented stories."""

    def test_counts_two_of_three_stories(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Two stories with passes=True out of three are counted."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [
                _make_story("US-001", "Alpha", passes=True, notes="Already done"),
                _make_story("US-002", "Beta", passes=False),
                _make_story("US-003", "Gamma", passes=True, notes="Already done"),
            ]
        )

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "2 stories detected as already implemented" in out

    def test_counts_single_story(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A single already-implemented story is counted."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file([_make_story("US-001", "Solo", passes=True, notes="Done")])

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "1 stories detected as already implemented" in out

    def test_counts_all_stories(self, capsys: pytest.CaptureFixture[str]) -> None:
        """All stories detected when all have passes=True."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [
                _make_story("US-001", "A", passes=True, notes="Done"),
                _make_story("US-002", "B", passes=True, notes="Done"),
                _make_story("US-003", "C", passes=True, notes="Done"),
            ]
        )

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "3 stories detected as already implemented" in out

    def test_logs_each_story_id_and_title(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Each already-implemented story shows its ID and title."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [
                _make_story("US-010", "Auth module", passes=True, notes="Found"),
                _make_story("US-020", "DB layer", passes=False),
                _make_story("US-030", "REST API", passes=True, notes="Found"),
            ]
        )

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "US-010:" in out
        assert "Auth module" in out
        assert "US-030:" in out
        assert "REST API" in out
        # US-020 should NOT appear (passes=False)
        assert "US-020" not in out
        assert "DB layer" not in out

    def test_notes_retained_after_logging(self) -> None:
        """Logging does not modify the notes on already-implemented stories."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [
                _make_story(
                    "US-001",
                    "Widget",
                    passes=True,
                    notes="Already implemented: widget.py exists",
                ),
            ]
        )

        _log_already_implemented(model)

        assert model.user_stories[0].notes == "Already implemented: widget.py exists"

    def test_tasks_command_logs_already_implemented_from_claude_output(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: tasks command logs already-implemented stories from Claude output."""
        from typer.testing import CliRunner

        from ralph.cli import app

        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "SPEC.md").write_text("# Spec")

        valid_json = _tasks_json_payload(
            [
                _make_story("US-001", "Auth", passes=True, notes="Found auth.py"),
                _make_story("US-002", "Config", passes=True, notes="Found config.py"),
                _make_story("US-003", "Dashboard", passes=False),
            ]
        )

        mock_instance = MagicMock()
        mock_instance.run_print_mode.return_value = (valid_json, 0)

        runner = CliRunner()
        with working_directory(tmp_path):
            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

        assert result.exit_code == 0
        assert "2 stories detected as already implemented" in result.output
        assert "US-001:" in result.output
        assert "Auth" in result.output
        assert "US-002:" in result.output
        assert "Config" in result.output


# ---------------------------------------------------------------------------
# AC-3: Console summary message format
# ---------------------------------------------------------------------------


class TestSummaryMessageFormat:
    """Verify the exact console message format for already-implemented stories."""

    def test_summary_contains_tasks_prefix(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Summary line must include the [Tasks] prefix."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file([_make_story("US-001", "Story", passes=True, notes="Done")])

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "[Tasks]" in out

    def test_summary_format_complete(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Full format: '[Tasks] N stories detected as already implemented'."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [
                _make_story("US-001", "A", passes=True, notes="Done"),
                _make_story("US-002", "B", passes=True, notes="Done"),
            ]
        )

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "[Tasks] 2 stories detected as already implemented" in out

    def test_each_story_indented_with_id_colon_title(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Each story line should show 'ID: title' format."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [_make_story("US-042", "Enable logging", passes=True, notes="Done")]
        )

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert "US-042:" in out
        assert "Enable logging" in out

    def test_format_through_tasks_cli_command(self, tmp_path: Path) -> None:
        """End-to-end: the tasks CLI command shows the formatted message."""
        from typer.testing import CliRunner

        from ralph.cli import app

        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "SPEC.md").write_text("# Spec")

        valid_json = _tasks_json_payload(
            [
                _make_story("US-001", "First", passes=True, notes="Exists"),
                _make_story("US-002", "Second", passes=False),
            ]
        )

        mock_instance = MagicMock()
        mock_instance.run_print_mode.return_value = (valid_json, 0)

        runner = CliRunner()
        with working_directory(tmp_path):
            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

        assert result.exit_code == 0
        assert "[Tasks]" in result.output
        assert "1 stories detected as already implemented" in result.output
        assert "US-001:" in result.output
        assert "First" in result.output


# ---------------------------------------------------------------------------
# AC-4: Normal operation when no stories are detected as already implemented
# ---------------------------------------------------------------------------


class TestNoStoriesDetected:
    """Verify behaviour when no stories have passes=True."""

    def test_no_output_from_log_function(self, capsys: pytest.CaptureFixture[str]) -> None:
        """_log_already_implemented produces no output when all passes=False."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file(
            [
                _make_story("US-001", "New feature", passes=False),
                _make_story("US-002", "Another feature", passes=False),
            ]
        )

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert out == ""

    def test_no_output_with_empty_story_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        """_log_already_implemented produces no output with no stories at all."""
        from ralph.commands.tasks import _log_already_implemented

        model = _make_tasks_file([])

        _log_already_implemented(model)

        out = capsys.readouterr().out
        assert out == ""

    def test_tasks_command_omits_detection_message_when_none_detected(self, tmp_path: Path) -> None:
        """End-to-end: no detection message when all stories have passes=False."""
        from typer.testing import CliRunner

        from ralph.cli import app

        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "SPEC.md").write_text("# Spec")

        valid_json = _tasks_json_payload(
            [
                _make_story("US-001", "New", passes=False),
                _make_story("US-002", "Also new", passes=False),
            ]
        )

        mock_instance = MagicMock()
        mock_instance.run_print_mode.return_value = (valid_json, 0)

        runner = CliRunner()
        with working_directory(tmp_path):
            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

        assert result.exit_code == 0
        assert "stories detected as already implemented" not in result.output
        assert "[Tasks]" not in result.output
        # Normal completion message should still appear
        assert "Generated 2 user stories" in result.output

    def test_tasks_command_succeeds_normally_without_detection(self, tmp_path: Path) -> None:
        """End-to-end: tasks command completes normally without detection output."""
        from typer.testing import CliRunner

        from ralph.cli import app

        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "SPEC.md").write_text("# Spec\n\nBuild a widget.")

        valid_json = _tasks_json_payload(
            [
                _make_story("US-001", "Create widget", passes=False),
            ]
        )

        mock_instance = MagicMock()
        mock_instance.run_print_mode.return_value = (valid_json, 0)

        runner = CliRunner()
        with working_directory(tmp_path):
            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

        assert result.exit_code == 0
        assert "Generated 1 user stories" in result.output
        # The output file should be written successfully
        tasks_path = tmp_path / "plans" / "TASKS.json"
        assert tasks_path.exists()
