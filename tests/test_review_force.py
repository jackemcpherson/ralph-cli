"""Tests for ralph review --force flag behavior."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ralph.cli import app
from ralph.models.reviewer import ReviewerConfig, ReviewerLevel


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    """Context manager that temporarily changes working directory."""
    original_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


def _write_claude_md_with_reviewers(path: Path, reviewer_names: list[str]) -> None:
    """Write a CLAUDE.md with the given reviewer names in RALPH:REVIEWERS markers."""
    lines = ["reviewers:"]
    for name in reviewer_names:
        lines.append(f"  - name: {name}")
        lines.append(f"    skill: reviewers/{name}")
        lines.append("    level: blocking")

    yaml_content = "\n".join(lines)
    content = (
        "# Project Instructions\n\n"
        "## Reviewers\n\n"
        "<!-- RALPH:REVIEWERS:START -->\n"
        f"```yaml\n{yaml_content}\n```\n"
        "<!-- RALPH:REVIEWERS:END -->\n\n"
        "## Project-Specific Instructions\n"
    )
    path.write_text(content, encoding="utf-8")


def _make_reviewers(names: list[str]) -> list[ReviewerConfig]:
    """Create ReviewerConfig objects from a list of names."""
    return [
        ReviewerConfig(
            name=name,
            skill=f"reviewers/{name}",
            level=ReviewerLevel.blocking,
        )
        for name in names
    ]


class TestReviewForceFlag:
    """Tests for --force flag on ralph review command."""

    def test_force_re_detects_and_overwrites_config(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that --force re-runs detection and overwrites existing config."""
        claude_md_path = tmp_path / "CLAUDE.md"
        _write_claude_md_with_reviewers(claude_md_path, ["code-simplifier"])
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        new_reviewers = _make_reviewers(["code-simplifier", "repo-structure", "python-code"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=new_reviewers),
                patch("ralph.commands.review.write_reviewer_config") as mock_write,
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch(
                    "ralph.commands.review.load_reviewer_configs",
                    return_value=_make_reviewers(["code-simplifier"]),
                ),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="test", success=True, skipped=False, attempts=1, error=None
                )
                mock_service_cls.return_value = mock_service

                runner.invoke(app, ["review", "--force"])

        mock_write.assert_called_once_with(claude_md_path, new_reviewers)

    def test_force_displays_added_reviewers(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --force displays which reviewers were added."""
        claude_md_path = tmp_path / "CLAUDE.md"
        _write_claude_md_with_reviewers(claude_md_path, ["code-simplifier"])
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        old_reviewers = _make_reviewers(["code-simplifier"])
        new_reviewers = _make_reviewers(["code-simplifier", "python-code", "test-quality"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=new_reviewers),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=old_reviewers),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="test", success=True, skipped=False, attempts=1, error=None
                )
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["review", "--force"])

        assert "Configuration Changes" in result.output
        assert "python-code" in result.output
        assert "test-quality" in result.output

    def test_force_displays_removed_reviewers(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --force displays which reviewers were removed."""
        claude_md_path = tmp_path / "CLAUDE.md"
        _write_claude_md_with_reviewers(
            claude_md_path, ["code-simplifier", "bicep", "github-actions"]
        )
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        old_reviewers = _make_reviewers(["code-simplifier", "bicep", "github-actions"])
        new_reviewers = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=new_reviewers),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=old_reviewers),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="test", success=True, skipped=False, attempts=1, error=None
                )
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["review", "--force"])

        assert "Configuration Changes" in result.output
        assert "bicep" in result.output
        assert "github-actions" in result.output

    def test_force_displays_no_changes_when_config_unchanged(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that --force displays 'no changes' when detection matches existing config."""
        claude_md_path = tmp_path / "CLAUDE.md"
        _write_claude_md_with_reviewers(claude_md_path, ["code-simplifier", "repo-structure"])
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        same_reviewers = _make_reviewers(["code-simplifier", "repo-structure"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=same_reviewers),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=same_reviewers),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="test", success=True, skipped=False, attempts=1, error=None
                )
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["review", "--force"])

        assert "No changes detected" in result.output

    def test_force_with_no_existing_config_behaves_as_first_run(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that --force with no existing config acts like first run."""
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        detected_reviewers = _make_reviewers(["code-simplifier", "repo-structure"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=detected_reviewers),
                patch("ralph.commands.review.write_reviewer_config") as mock_write,
                patch("ralph.commands.review.has_reviewer_config", return_value=False),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="test", success=True, skipped=False, attempts=1, error=None
                )
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["review", "--force"])

        assert "First run detected" in result.output
        mock_write.assert_called_once()

    def test_force_shows_both_added_and_removed(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --force shows both added and removed reviewers together."""
        claude_md_path = tmp_path / "CLAUDE.md"
        _write_claude_md_with_reviewers(claude_md_path, ["code-simplifier", "bicep"])
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        old_reviewers = _make_reviewers(["code-simplifier", "bicep"])
        new_reviewers = _make_reviewers(["code-simplifier", "python-code"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=new_reviewers),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=old_reviewers),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="test", success=True, skipped=False, attempts=1, error=None
                )
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["review", "--force"])

        assert "Configuration Changes" in result.output
        assert "python-code" in result.output
        assert "bicep" in result.output

    def test_force_still_executes_review_loop(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --force still runs the review loop after updating config."""
        claude_md_path = tmp_path / "CLAUDE.md"
        _write_claude_md_with_reviewers(claude_md_path, ["code-simplifier"])
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

        reviewers = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.ReviewLoopService") as mock_service_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.run_reviewer.return_value = MagicMock(
                    reviewer_name="code-simplifier",
                    success=True,
                    skipped=False,
                    attempts=1,
                    error=None,
                )
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["review", "--force"])

        mock_service.run_reviewer.assert_called_once()
        assert "Review Summary" in result.output
