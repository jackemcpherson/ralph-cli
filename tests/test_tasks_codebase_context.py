"""Tests for codebase context gathering in ralph tasks command.

Tests for US-008: Add codebase context to ralph tasks prompt.
Verifies that _gather_codebase_summary() and _iter_file_tree() produce
correct output and that _build_prompt_from_skill() includes codebase context.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.models import TasksFile


class TestIterFileTree:
    """Tests for _iter_file_tree directory scanning."""

    def test_lists_files_and_directories(self, tmp_path: Path) -> None:
        """Test that file tree includes both files and directories."""
        from ralph.commands.tasks import _iter_file_tree

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Readme")

        lines = list(_iter_file_tree(tmp_path))

        assert any("src/" in line for line in lines)
        assert any("main.py" in line for line in lines)
        assert any("README.md" in line for line in lines)

    def test_excludes_git_and_venv_dirs(self, tmp_path: Path) -> None:
        """Test that .git, .venv, and __pycache__ are excluded."""
        from ralph.commands.tasks import _iter_file_tree

        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("")

        lines = list(_iter_file_tree(tmp_path))
        joined = "\n".join(lines)

        assert ".git" not in joined
        assert ".venv" not in joined
        assert "__pycache__" not in joined
        assert "src/" in joined

    def test_respects_max_depth(self, tmp_path: Path) -> None:
        """Test that tree scanning stops at max_depth."""
        from ralph.commands.tasks import _iter_file_tree

        # Create deeply nested structure
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "deep_file.txt").write_text("")

        lines = list(_iter_file_tree(tmp_path, max_depth=2))
        joined = "\n".join(lines)

        # Should have the top levels but not deep_file.txt
        assert "a/" in joined
        assert "deep_file.txt" not in joined
        assert "..." in joined  # truncation marker

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty directories produce no file entries."""
        from ralph.commands.tasks import _iter_file_tree

        lines = list(_iter_file_tree(tmp_path))

        assert lines == []

    def test_excludes_egg_info_dirs(self, tmp_path: Path) -> None:
        """Test that .egg-info directories are excluded."""
        from ralph.commands.tasks import _iter_file_tree

        (tmp_path / "my_package.egg-info").mkdir()
        (tmp_path / "my_package.egg-info" / "PKG-INFO").write_text("")
        (tmp_path / "setup.py").write_text("")

        lines = list(_iter_file_tree(tmp_path))
        joined = "\n".join(lines)

        assert "egg-info" not in joined
        assert "setup.py" in joined


class TestGatherCodebaseSummary:
    """Tests for _gather_codebase_summary function."""

    def test_includes_file_tree_section(self, tmp_path: Path) -> None:
        """Test that summary includes a file tree section."""
        from ralph.commands.tasks import _gather_codebase_summary

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        summary = _gather_codebase_summary(tmp_path)

        assert "### File Tree" in summary
        assert "src/" in summary
        assert "main.py" in summary

    def test_includes_pyproject_toml_content(self, tmp_path: Path) -> None:
        """Test that summary includes pyproject.toml content when present."""
        from ralph.commands.tasks import _gather_codebase_summary

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\nversion = "1.0.0"\n'
        )

        summary = _gather_codebase_summary(tmp_path)

        assert "### pyproject.toml" in summary
        assert 'name = "test-project"' in summary

    def test_includes_readme_content(self, tmp_path: Path) -> None:
        """Test that summary includes README.md content when present."""
        from ralph.commands.tasks import _gather_codebase_summary

        (tmp_path / "README.md").write_text("# My Project\n\nA test project.")

        summary = _gather_codebase_summary(tmp_path)

        assert "### README.md" in summary
        assert "# My Project" in summary

    def test_skips_missing_key_files(self, tmp_path: Path) -> None:
        """Test that summary gracefully skips missing key files."""
        from ralph.commands.tasks import _gather_codebase_summary

        # No key files exist
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("")

        summary = _gather_codebase_summary(tmp_path)

        # Should still have file tree but no key file sections
        assert "### File Tree" in summary
        assert "### pyproject.toml" not in summary
        assert "### README.md" not in summary

    def test_truncates_large_file_content(self, tmp_path: Path) -> None:
        """Test that individual file content over 3000 chars is truncated."""
        from ralph.commands.tasks import _gather_codebase_summary

        large_content = "x" * 5000
        (tmp_path / "pyproject.toml").write_text(large_content)

        summary = _gather_codebase_summary(tmp_path)

        assert "... (truncated)" in summary

    def test_returns_string(self, tmp_path: Path) -> None:
        """Test that summary is always a string."""
        from ralph.commands.tasks import _gather_codebase_summary

        summary = _gather_codebase_summary(tmp_path)

        assert isinstance(summary, str)


class TestBuildPromptIncludesCodebaseContext:
    """Tests for _build_prompt_from_skill including codebase context."""

    def test_prompt_includes_codebase_summary(self, tmp_path: Path) -> None:
        """Test that the prompt includes the codebase summary section."""
        from ralph.commands.tasks import _build_prompt_from_skill

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("Test spec content")

        assert "## Existing Codebase Summary" in prompt

    def test_prompt_includes_already_implemented_instructions(self, tmp_path: Path) -> None:
        """Test that the prompt instructs Claude about already-implemented detection."""
        from ralph.commands.tasks import _build_prompt_from_skill

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("Test spec content")

        assert "## Instructions for Already-Implemented Detection" in prompt
        assert "passes: true" in prompt
        assert "already implemented" in prompt.lower()

    def test_prompt_still_includes_spec_content(self, tmp_path: Path) -> None:
        """Test that the prompt still contains the spec content."""
        from ralph.commands.tasks import _build_prompt_from_skill

        spec = "# My Feature\n\nThis is the spec."

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill(spec)

        assert spec in prompt

    def test_prompt_includes_branch_name_when_provided(self, tmp_path: Path) -> None:
        """Test that branch name is included when provided."""
        from ralph.commands.tasks import _build_prompt_from_skill

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("spec", branch_name="ralph/my-feature")

        assert "ralph/my-feature" in prompt

    def test_prompt_includes_file_tree_from_cwd(self, tmp_path: Path) -> None:
        """Test that the prompt includes the file tree from the current working directory."""
        from ralph.commands.tasks import _build_prompt_from_skill

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')")

        with patch("ralph.commands.tasks.Path.cwd", return_value=tmp_path):
            prompt = _build_prompt_from_skill("spec")

        assert "### File Tree" in prompt
        assert "app.py" in prompt


class TestLogAlreadyImplemented:
    """Tests for _log_already_implemented console output."""

    @staticmethod
    def _make_tasks_file(
        stories: list[dict[str, object]],
    ) -> TasksFile:
        return TasksFile(
            project="TestProject",
            branch_name="ralph/test",
            description="Test",
            user_stories=stories,
        )

    def test_logs_count_when_stories_detected(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that summary line shows correct count of already-implemented stories."""
        from ralph.commands.tasks import _log_already_implemented

        tasks_model = self._make_tasks_file(
            [
                {
                    "id": "US-001",
                    "title": "First story",
                    "description": "Desc",
                    "priority": 1,
                    "passes": True,
                    "notes": "Already implemented: found in codebase",
                },
                {
                    "id": "US-002",
                    "title": "Second story",
                    "description": "Desc",
                    "priority": 2,
                    "passes": False,
                    "notes": "",
                },
                {
                    "id": "US-003",
                    "title": "Third story",
                    "description": "Desc",
                    "priority": 3,
                    "passes": True,
                    "notes": "Already implemented: evidence",
                },
            ]
        )

        _log_already_implemented(tasks_model)

        captured = capsys.readouterr().out
        assert "2 stories detected as already implemented" in captured

    def test_logs_each_story_id_and_title(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that each already-implemented story ID and title are displayed."""
        from ralph.commands.tasks import _log_already_implemented

        tasks_model = self._make_tasks_file(
            [
                {
                    "id": "US-001",
                    "title": "Auth module",
                    "description": "Desc",
                    "priority": 1,
                    "passes": True,
                    "notes": "Already implemented",
                },
                {
                    "id": "US-002",
                    "title": "API endpoint",
                    "description": "Desc",
                    "priority": 2,
                    "passes": True,
                    "notes": "Already implemented",
                },
            ]
        )

        _log_already_implemented(tasks_model)

        captured = capsys.readouterr().out
        assert "US-001:" in captured
        assert "Auth module" in captured
        assert "US-002:" in captured
        assert "API endpoint" in captured

    def test_no_output_when_no_stories_detected(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that nothing is logged when no stories are detected as already implemented."""
        from ralph.commands.tasks import _log_already_implemented

        tasks_model = self._make_tasks_file(
            [
                {
                    "id": "US-001",
                    "title": "New story",
                    "description": "Desc",
                    "priority": 1,
                    "passes": False,
                    "notes": "",
                },
            ]
        )

        _log_already_implemented(tasks_model)

        captured = capsys.readouterr().out
        assert captured == ""

    def test_notes_are_retained_on_already_implemented_stories(self) -> None:
        """Test that stories detected as already-implemented retain their notes."""
        from ralph.commands.tasks import _log_already_implemented

        tasks_model = self._make_tasks_file(
            [
                {
                    "id": "US-001",
                    "title": "Auth module",
                    "description": "Desc",
                    "priority": 1,
                    "passes": True,
                    "notes": "Already implemented: found auth.py with login()",
                },
            ]
        )

        _log_already_implemented(tasks_model)

        # Verify notes are still present on the model (not stripped by logging)
        story = tasks_model.user_stories[0]
        assert story.notes == "Already implemented: found auth.py with login()"

    def test_summary_format_matches_spec(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that the summary format is '[Tasks] N stories detected as already implemented'."""
        from ralph.commands.tasks import _log_already_implemented

        tasks_model = self._make_tasks_file(
            [
                {
                    "id": "US-001",
                    "title": "Story one",
                    "description": "Desc",
                    "priority": 1,
                    "passes": True,
                    "notes": "Already implemented",
                },
            ]
        )

        _log_already_implemented(tasks_model)

        captured = capsys.readouterr().out
        assert "[Tasks]" in captured
        assert "1 stories detected as already implemented" in captured


class TestCodebaseContextIntegration:
    """Integration-level tests for codebase context in the tasks command."""

    @pytest.fixture
    def project_with_spec_and_src(self, tmp_path: Path) -> Path:
        """Create a project with spec, source, and ralph/tasks skill."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "SPEC.md").write_text("# Feature Spec\n\nBuild a widget.")

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "widget-app"\n')

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "widget.py").write_text("class Widget:\n    pass\n")

        skill_dir = tmp_path / "skills" / "ralph" / "tasks"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ralph-tasks\ndescription: Test tasks skill\n---\n\n"
            "# Ralph Tasks Skill\n\nConvert PRD to TASKS.json."
        )

        return tmp_path

    def test_tasks_command_sends_codebase_context_to_claude(
        self, project_with_spec_and_src: Path
    ) -> None:
        """Test that the tasks command includes codebase context in the Claude prompt."""
        import json
        from unittest.mock import MagicMock

        from typer.testing import CliRunner

        from ralph.cli import app

        valid_tasks_json = json.dumps(
            {
                "project": "WidgetApp",
                "branchName": "ralph/widget-app",
                "description": "Widget feature",
                "userStories": [
                    {
                        "id": "US-001",
                        "title": "Build widget",
                        "description": "As a user, I want a widget",
                        "acceptanceCriteria": ["Widget exists"],
                        "priority": 1,
                        "passes": False,
                        "notes": "",
                    }
                ],
            }
        )

        captured_prompt: list[str] = []
        runner = CliRunner()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_with_spec_and_src)

            mock_instance = MagicMock()

            def capture_run(*args: object, **kwargs: object) -> tuple[str, int]:
                if args:
                    captured_prompt.append(str(args[0]))
                return (valid_tasks_json, 0)

            mock_instance.run_print_mode.side_effect = capture_run

            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert len(captured_prompt) > 0
        # The prompt sent to Claude should include codebase context
        assert "Existing Codebase Summary" in captured_prompt[0]
        assert "widget.py" in captured_prompt[0]
        assert "Already-Implemented Detection" in captured_prompt[0]
