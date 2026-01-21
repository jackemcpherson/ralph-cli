"""Integration tests for Ralph CLI commands.

Focused integration tests for happy path of each command:
- ralph init
- ralph prd
- ralph tasks
- ralph once
- ralph loop
- ralph sync
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph import __version__
from ralph.cli import app


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    """Context manager that temporarily changes working directory."""
    original_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Create a temporary Python project with pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")
    return tmp_path


@pytest.fixture
def project_with_skill(tmp_path: Path) -> Path:
    """Create a project with ralph-prd skill."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")
    (tmp_path / "plans").mkdir()

    skill_dir = tmp_path / "skills" / "ralph-prd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ralph-prd\ndescription: Test PRD skill\n---\n\n"
        "# Ralph PRD Skill\n\nYou are helping create a PRD."
    )
    return tmp_path


@pytest.fixture
def project_with_spec(tmp_path: Path) -> Path:
    """Create a project with SPEC.md and ralph-tasks skill."""
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()

    (plans_dir / "SPEC.md").write_text("# Feature Spec\n\nTest specification.")

    skill_dir = tmp_path / "skills" / "ralph-tasks"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ralph-tasks\ndescription: Test tasks skill\n---\n\n"
        "# Ralph Tasks Skill\n\nConvert PRD to TASKS.json."
    )

    return tmp_path


@pytest.fixture
def project_with_tasks(tmp_path: Path) -> Path:
    """Create a project with TASKS.json, PROGRESS.txt, and skill."""
    sample_tasks = {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "First story",
                "description": "As a user, I want feature A",
                "acceptanceCriteria": ["Criterion 1"],
                "priority": 1,
                "passes": False,
                "notes": "",
            },
        ],
    }

    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    (plans_dir / "TASKS.json").write_text(json.dumps(sample_tasks, indent=2))
    (plans_dir / "PROGRESS.txt").write_text("# Progress Log\n\n")

    skill_dir = tmp_path / "skills" / "ralph-iteration"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ralph-iteration\ndescription: Test iteration skill\n---\n\n"
        "# Ralph Iteration Skill\n\nYou are an autonomous agent.\n"
        "Output <ralph>COMPLETE</ralph> when done."
    )

    return tmp_path


@pytest.fixture
def skills_dir(python_project: Path) -> Path:
    """Create a skills directory with a valid skill."""
    skills_path = python_project / "skills"
    skills_path.mkdir()

    skill_path = skills_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text(
        '---\nname: "test-skill"\ndescription: "A test skill"\n---\n\n# Test Skill\n'
    )

    return skills_path


class TestCliHelp:
    """Tests for CLI help and version."""

    def test_help_shows_all_commands(self, runner: CliRunner) -> None:
        """Test that --help shows all registered commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        for cmd in ["init", "prd", "tasks", "once", "loop", "sync"]:
            assert cmd in result.output

    def test_version_shows_version_number(self, runner: CliRunner) -> None:
        """Test that --version shows the package version."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output


class TestInitCommand:
    """Integration tests for ralph init command."""

    def test_init_creates_all_ralph_files(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init creates all required Ralph workflow files."""
        with working_directory(python_project):
            mock_instance = MagicMock()
            mock_instance.run_interactive.return_value = 0

            with (
                patch("ralph.commands.init_cmd.ClaudeService", return_value=mock_instance),
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert (python_project / "plans").is_dir()
        assert (python_project / "plans" / "SPEC.md").is_file()
        assert (python_project / "plans" / "TASKS.json").is_file()
        assert (python_project / "plans" / "PROGRESS.txt").is_file()
        assert (python_project / "CLAUDE.md").is_file()
        assert (python_project / "AGENTS.md").is_file()
        assert (python_project / "CHANGELOG.md").is_file()

    def test_init_with_skip_claude_flag(self, runner: CliRunner, python_project: Path) -> None:
        """Test that --skip-claude flag prevents Claude invocation."""
        with working_directory(python_project):
            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                result = runner.invoke(app, ["init", "--skip-claude"])

        assert result.exit_code == 0
        mock_claude.assert_not_called()
        assert (python_project / "CLAUDE.md").is_file()


class TestPrdCommand:
    """Integration tests for ralph prd command."""

    def test_prd_uses_skip_permissions(self, runner: CliRunner, project_with_skill: Path) -> None:
        """Test that ralph prd uses skip_permissions=True."""
        captured_kwargs: dict[str, Any] = {}

        with working_directory(project_with_skill):
            mock_instance = MagicMock()
            mock_instance.run_interactive.side_effect = (
                lambda *a, **kw: captured_kwargs.update(kw) or 0
            )

            with patch("ralph.commands.prd.ClaudeService", return_value=mock_instance):
                runner.invoke(app, ["prd"])

        assert captured_kwargs.get("skip_permissions") is True

    def test_prd_uses_autonomous_mode_prompt(
        self, runner: CliRunner, project_with_skill: Path
    ) -> None:
        """Test that ralph prd uses append_system_prompt kwarg."""
        captured_kwargs: dict[str, Any] = {}

        with working_directory(project_with_skill):
            mock_instance = MagicMock()
            mock_instance.run_interactive.side_effect = (
                lambda *a, **kw: captured_kwargs.update(kw) or 0
            )

            with patch("ralph.commands.prd.ClaudeService", return_value=mock_instance):
                runner.invoke(app, ["prd"])

        # Verify append_system_prompt was passed (the constant is accessed via mock)
        assert "append_system_prompt" in captured_kwargs
        assert captured_kwargs.get("append_system_prompt") is not None


class TestTasksCommand:
    """Integration tests for ralph tasks command."""

    def test_tasks_creates_tasks_json(self, runner: CliRunner, project_with_spec: Path) -> None:
        """Test that ralph tasks creates TASKS.json from spec."""
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
                        "acceptanceCriteria": ["Criterion 1"],
                        "priority": 1,
                        "passes": False,
                        "notes": "",
                    }
                ],
            }
        )

        with working_directory(project_with_spec):
            mock_instance = MagicMock()
            mock_instance.run_print_mode.return_value = (valid_tasks_json, 0)

            with patch("ralph.commands.tasks.ClaudeService", return_value=mock_instance):
                result = runner.invoke(app, ["tasks", "plans/SPEC.md"])

        assert result.exit_code == 0
        tasks_file = project_with_spec / "plans" / "TASKS.json"
        assert tasks_file.exists()


class TestOnceCommand:
    """Integration tests for ralph once command."""

    def test_once_runs_and_shows_story_info(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once runs, displays story info, and streams Claude output."""

        def mock_popen(args: list[str], **kwargs: Any) -> MagicMock:
            mock_process = MagicMock()
            json_output = json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Implementing feature <ralph>COMPLETE</ralph>"}
                        ]
                    },
                }
            )
            mock_process.stdout = StringIO(json_output + "\n")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        with working_directory(project_with_tasks):
            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["once"])

        # Verify story info is displayed
        assert "US-001" in result.output
        assert "First story" in result.output
        # Verify Claude output was streamed
        assert "Implementing feature" in result.output
        # Verify COMPLETE tag detected
        assert "All stories are now complete" in result.output

    def test_once_uses_stream_json_format(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once uses stream-json format."""
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs: Any) -> MagicMock:
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Done")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        with working_directory(project_with_tasks):
            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["once"])

        assert "--output-format" in captured_args
        format_idx = captured_args.index("--output-format")
        assert captured_args[format_idx + 1] == "stream-json"

    def test_once_uses_append_system_prompt_flag(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph once passes --append-system-prompt flag."""
        from ralph.services import ClaudeService

        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs: Any) -> MagicMock:
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Done")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        with working_directory(project_with_tasks):
            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["once"])

        assert "--append-system-prompt" in captured_args
        prompt_idx = captured_args.index("--append-system-prompt")
        assert captured_args[prompt_idx + 1] == ClaudeService.AUTONOMOUS_MODE_PROMPT


class TestLoopCommand:
    """Integration tests for ralph loop command."""

    def test_loop_runs_and_shows_iteration_progress(
        self, runner: CliRunner, project_with_tasks: Path
    ) -> None:
        """Test that ralph loop runs iterations and shows progress."""

        def mock_popen(args: list[str], **kwargs: Any) -> MagicMock:
            mock_process = MagicMock()
            json_output = json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "Story done <ralph>COMPLETE</ralph>"}]
                    },
                }
            )
            mock_process.stdout = StringIO(json_output + "\n")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        with working_directory(project_with_tasks):
            with (
                patch("subprocess.Popen", side_effect=mock_popen),
                patch("ralph.commands.loop._setup_branch", return_value=True),
            ):
                result = runner.invoke(app, ["loop", "1"])

        assert result.exit_code == 0
        # Verify story iteration format: [1/1] US-001: First story
        assert "[1/1]" in result.output
        assert "US-001" in result.output
        assert "First story" in result.output
        # Verify loop summary is shown
        assert "Loop Summary" in result.output
        assert "All stories complete" in result.output


class TestSyncCommand:
    """Integration tests for ralph sync command."""

    def test_sync_copies_valid_skill(
        self,
        runner: CliRunner,
        python_project: Path,
        skills_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that sync copies valid skills to target directory."""
        from ralph.services import SkillSyncResult, SyncStatus

        with working_directory(python_project):
            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [skills_dir / "test-skill"]
                mock_service.target_dir = tmp_path / "target"

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.CREATED,
                    source_path=skills_dir / "test-skill",
                    target_path=tmp_path / "target" / "test-skill",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

        assert result.exit_code == 0
        assert "test-skill" in result.output
        assert "Synced 1 skill" in result.output

    def test_sync_shows_warning_when_no_skills_dir(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that sync shows message when skills/ doesn't exist."""
        with working_directory(python_project):
            result = runner.invoke(app, ["sync"])

        assert result.exit_code == 0
        assert "Skills directory not found" in result.output

    def test_sync_remove_flag_works(
        self,
        runner: CliRunner,
        python_project: Path,
        skills_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that sync --remove removes installed skills."""
        with working_directory(python_project):
            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.remove_skills.return_value = ["test-skill"]

                result = runner.invoke(app, ["sync", "--remove"])

        assert result.exit_code == 0
        assert "test-skill" in result.output


class TestBuildSkillPrompt:
    """Tests for build_skill_prompt utility."""

    def test_prompt_starts_with_at_file_reference(self, tmp_path: Path) -> None:
        """Test that build_skill_prompt creates @file reference."""
        from ralph.utils import build_skill_prompt

        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Test Skill")

        result = build_skill_prompt(tmp_path, "test-skill", "Some context")

        assert result.startswith("Follow the instructions in @skills/test-skill/SKILL.md")

    def test_prompt_includes_context(self, tmp_path: Path) -> None:
        """Test that build_skill_prompt appends context."""
        from ralph.utils import build_skill_prompt

        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Test Skill")

        context = "## Context\n\nThis is test context."
        result = build_skill_prompt(tmp_path, "test-skill", context)

        assert context in result
        assert "@skills/test-skill/SKILL.md" in result

    def test_prompt_raises_for_missing_skill(self, tmp_path: Path) -> None:
        """Test that build_skill_prompt raises SkillNotFoundError for missing skill."""
        from ralph.services import SkillNotFoundError
        from ralph.utils import build_skill_prompt

        (tmp_path / "skills").mkdir()

        with pytest.raises(SkillNotFoundError):
            build_skill_prompt(tmp_path, "nonexistent-skill", "context")


class TestOnceCommandPromptFormat:
    """Tests for ralph once command prompt format."""

    def test_once_prompt_uses_at_file_reference(self, project_with_tasks: Path) -> None:
        """Test that ralph once uses @file reference in prompt."""
        captured_prompt: list[str] = []

        def mock_popen(args: list[str], **kwargs: Any) -> MagicMock:
            # Find the --print flag and capture the prompt (next arg)
            if "--print" in args:
                idx = args.index("--print")
                if idx + 1 < len(args):
                    captured_prompt.append(args[idx + 1])
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Done")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        with working_directory(project_with_tasks):
            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner = CliRunner()
                runner.invoke(app, ["once"])

        assert len(captured_prompt) > 0
        assert "@skills/ralph-iteration/SKILL.md" in captured_prompt[0]
