"""Tests for --no-fix and resumable review features in loop.py code paths.

Covers loop.py-specific paths that are NOT tested in test_review_command.py:
- --no-fix flag skipping FixLoopService calls in ReviewLoopService.run_review_loop()
- --no-fix summary output in _run_review_loop() (loop.py)
- Resume logic in _run_review_loop() (loop.py)
- State file cleanup in _run_review_loop() (loop.py)
- Config change invalidation in _run_review_loop() (loop.py)

Review command (review.py) tests live in test_review_command.py.
ReviewState model tests live in test_review_state.py.
"""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph.models import REVIEW_STATE_FILENAME, ReviewState
from ralph.models.finding import Finding, ReviewOutput, Verdict
from ralph.models.reviewer import ReviewerConfig, ReviewerLevel
from ralph.services.review_loop import ReviewerResult, ReviewLoopService


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    """Context manager that temporarily changes working directory."""
    original_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


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


def _make_mock_service() -> MagicMock:
    """Create a mock ReviewLoopService with default passing behavior."""
    mock_service = MagicMock()
    mock_service.should_run_reviewer.return_value = True
    mock_service.is_enforced.return_value = True
    mock_service.should_run_fix_loop.return_value = False
    mock_service.run_reviewer.return_value = ReviewerResult(
        reviewer_name="test",
        success=True,
        skipped=False,
        attempts=1,
        error=None,
        review_output=None,
        fix_skipped=False,
    )
    return mock_service


def _make_needs_work_output() -> ReviewOutput:
    """Create a ReviewOutput with NEEDS_WORK verdict and one finding."""
    return ReviewOutput(
        verdict=Verdict.NEEDS_WORK,
        findings=[
            Finding(
                id="FINDING-001",
                category="Type Safety",
                file_path="src/test.py",
                line_number=10,
                issue="Missing type annotation",
                suggestion="Add type hint",
            )
        ],
    )


# -----------------------------------------------------------------------
# 1. --no-fix skips FixLoopService calls in ReviewLoopService.run_review_loop()
# -----------------------------------------------------------------------


class TestNoFixSkipsFixLoopInService:
    """Verify --no-fix skips FixLoopService in run_review_loop()."""

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_prevents_fix_service_instantiation(
        self,
        mock_claude_class: MagicMock,
        mock_fix_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """FixLoopService is never instantiated when no_fix=True."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (
            _needs_work_structured_output(),
            0,
        )
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        service.run_review_loop([reviewer], set(), no_fix=True)

        mock_fix_class.assert_not_called()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_with_multiple_needs_work_reviewers(
        self,
        mock_claude_class: MagicMock,
        mock_fix_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """FixLoopService is never called even with multiple NEEDS_WORK reviewers."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (
            _needs_work_structured_output(),
            0,
        )
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skills(tmp_path, ["r1", "r2", "r3"])
        reviewers = [
            _create_reviewer(name="r1", skill="reviewers/r1"),
            _create_reviewer(name="r2", skill="reviewers/r2"),
            _create_reviewer(name="r3", skill="reviewers/r3"),
        ]

        results = service.run_review_loop(reviewers, set(), no_fix=True)

        mock_fix_class.assert_not_called()
        assert len(results) == 3
        assert all(r.fix_skipped for r in results)

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_false_invokes_fix_loop(
        self,
        mock_claude_class: MagicMock,
        mock_fix_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """FixLoopService IS called when no_fix=False (default behavior)."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (
            _needs_work_structured_output(),
            0,
        )
        mock_claude_class.return_value = mock_claude

        mock_fix = MagicMock()
        mock_fix.run_fix_loop.return_value = []
        mock_fix_class.return_value = mock_fix

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        results = service.run_review_loop([reviewer], set(), no_fix=False)

        mock_fix_class.assert_called_once()
        mock_fix.run_fix_loop.assert_called_once()
        assert results[0].fix_skipped is False

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_logs_skip_message_for_each_needs_work(
        self,
        mock_claude_class: MagicMock,
        mock_fix_class: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each NEEDS_WORK reviewer logs '[Fix] Skipped (--no-fix)'."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (
            _needs_work_structured_output(),
            0,
        )
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skills(tmp_path, ["r1", "r2"])
        reviewers = [
            _create_reviewer(name="r1", skill="reviewers/r1"),
            _create_reviewer(name="r2", skill="reviewers/r2"),
        ]

        with caplog.at_level(logging.INFO):
            service.run_review_loop(reviewers, set(), no_fix=True)

        skip_messages = [r for r in caplog.records if "[Fix] Skipped (--no-fix)" in r.message]
        assert len(skip_messages) == 2


# -----------------------------------------------------------------------
# 2. --no-fix summary output in _run_review_loop (loop.py)
# -----------------------------------------------------------------------


class TestNoFixSummaryLoopRunReviewLoop:
    """Verify --no-fix summary output in _run_review_loop (loop.py)."""

    def test_run_review_loop_no_fix_shows_findings_not_fixed(self, tmp_path: Path) -> None:
        """_run_review_loop shows 'findings (not fixed)' for NEEDS_WORK reviewers."""
        from ralph.commands.loop import _run_review_loop

        _setup_loop_project(tmp_path, ["test-quality"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.loop.load_reviewer_configs") as mock_load,
                patch("ralph.commands.loop.detect_languages", return_value=set()),
                patch("ralph.commands.loop.ReviewLoopService") as mock_cls,
            ):
                reviewers = _make_reviewers(["test-quality"])
                mock_load.return_value = reviewers

                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.should_run_fix_loop.return_value = True
                mock_service.run_reviewer.return_value = ReviewerResult(
                    reviewer_name="test-quality",
                    success=True,
                    skipped=False,
                    attempts=1,
                    review_output=_make_needs_work_output(),
                )
                mock_cls.return_value = mock_service

                from io import StringIO

                from rich.console import Console

                output = StringIO()
                test_console = Console(file=output, force_terminal=False, no_color=True)

                with patch("ralph.commands.loop.console", test_console):
                    _run_review_loop(
                        project_root=tmp_path,
                        progress_path=tmp_path / "plans" / "PROGRESS.txt",
                        strict=False,
                        verbose=False,
                        no_fix=True,
                    )

                text = output.getvalue()
                assert "findings (not fixed)" in text
                assert "test-quality" in text


# -----------------------------------------------------------------------
# 3. Resume logic in _run_review_loop (loop.py)
# -----------------------------------------------------------------------


class TestResumeInLoopRunReviewLoop:
    """Verify resume logic in _run_review_loop (loop.py)."""

    def test_run_review_loop_resume_skips_completed(self, tmp_path: Path) -> None:
        """_run_review_loop skips completed reviewers from state file."""
        from ralph.commands.loop import _run_review_loop

        _setup_loop_project(tmp_path, ["a", "b"])

        reviewers = _make_reviewers(["a", "b"])
        config_hash = ReviewState.compute_config_hash(reviewers)

        state = ReviewState(
            reviewer_names=["a", "b"],
            completed={"a": True},
            timestamp=datetime.now(UTC).isoformat(),
            config_hash=config_hash,
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.loop.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.loop.detect_languages", return_value=set()),
                patch("ralph.commands.loop.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service

                _run_review_loop(
                    project_root=tmp_path,
                    progress_path=tmp_path / "plans" / "PROGRESS.txt",
                    strict=False,
                    verbose=False,
                    resume_review=True,
                )

        # Only "b" should have been run
        assert mock_service.run_reviewer.call_count == 1


# -----------------------------------------------------------------------
# 4. State file cleanup in _run_review_loop (loop.py)
# -----------------------------------------------------------------------


class TestStateCleanupInLoopRunReviewLoop:
    """Verify state file cleanup in _run_review_loop (loop.py)."""

    def test_state_file_cleaned_up_after_completion(self, tmp_path: Path) -> None:
        """State file is removed after _run_review_loop completes successfully."""
        from ralph.commands.loop import _run_review_loop

        _setup_loop_project(tmp_path, ["a"])

        reviewers = _make_reviewers(["a"])
        state_path = tmp_path / REVIEW_STATE_FILENAME

        # Create a state file
        state = ReviewState(
            reviewer_names=["a"],
            completed={},
            timestamp=datetime.now(UTC).isoformat(),
            config_hash="any",
        )
        state.save(state_path)
        assert state_path.exists()

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.loop.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.loop.detect_languages", return_value=set()),
                patch("ralph.commands.loop.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                _run_review_loop(
                    project_root=tmp_path,
                    progress_path=tmp_path / "plans" / "PROGRESS.txt",
                    strict=False,
                    verbose=False,
                )

        assert not state_path.exists()


# -----------------------------------------------------------------------
# 5. Config change invalidation in _run_review_loop (loop.py)
# -----------------------------------------------------------------------


class TestConfigInvalidationInLoopRunReviewLoop:
    """Verify config change invalidation in _run_review_loop (loop.py)."""

    def test_stale_hash_runs_all_reviewers(self, tmp_path: Path) -> None:
        """_run_review_loop runs all reviewers when config hash mismatches."""
        from ralph.commands.loop import _run_review_loop

        _setup_loop_project(tmp_path, ["a", "b"])

        reviewers = _make_reviewers(["a", "b"])

        state = ReviewState(
            reviewer_names=["a", "b"],
            completed={"a": True},
            timestamp=datetime.now(UTC).isoformat(),
            config_hash="stale_hash",
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.loop.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.loop.detect_languages", return_value=set()),
                patch("ralph.commands.loop.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                _run_review_loop(
                    project_root=tmp_path,
                    progress_path=tmp_path / "plans" / "PROGRESS.txt",
                    strict=False,
                    verbose=False,
                    resume_review=True,
                )

        # Both should run because stale state is discarded
        assert mock_service.run_reviewer.call_count == 2

    def test_stale_hash_logs_console_message(self, tmp_path: Path) -> None:
        """_run_review_loop shows config change message on stale hash."""
        from io import StringIO

        from rich.console import Console

        from ralph.commands.loop import _run_review_loop

        _setup_loop_project(tmp_path, ["a"])

        reviewers = _make_reviewers(["a"])

        state = ReviewState(
            reviewer_names=["a"],
            completed={},
            timestamp=datetime.now(UTC).isoformat(),
            config_hash="stale",
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.loop.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.loop.detect_languages", return_value=set()),
                patch("ralph.commands.loop.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()

                output = StringIO()
                test_console = Console(file=output, force_terminal=False, no_color=True)

                with patch("ralph.commands.loop.console", test_console):
                    _run_review_loop(
                        project_root=tmp_path,
                        progress_path=tmp_path / "plans" / "PROGRESS.txt",
                        strict=False,
                        verbose=False,
                        resume_review=True,
                    )

                text = output.getvalue()
                assert "reviewer configuration has changed" in text


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _needs_work_structured_output() -> str:
    """Return structured output text with NEEDS_WORK verdict."""
    return """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""


def _create_service_with_skill(tmp_path: Path) -> ReviewLoopService:
    """Create a ReviewLoopService with a test skill."""
    skills_dir = tmp_path / "skills"
    (skills_dir / "reviewers" / "test-quality").mkdir(parents=True)
    (skills_dir / "reviewers" / "test-quality" / "SKILL.md").write_text("# Test")
    return ReviewLoopService(project_root=tmp_path, skills_dir=skills_dir)


def _create_service_with_skills(tmp_path: Path, skill_names: list[str]) -> ReviewLoopService:
    """Create a ReviewLoopService with multiple test skills."""
    skills_dir = tmp_path / "skills"
    for name in skill_names:
        skill_dir = skills_dir / "reviewers" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}")
    return ReviewLoopService(project_root=tmp_path, skills_dir=skills_dir)


def _create_reviewer(
    name: str = "test-quality",
    skill: str = "reviewers/test-quality",
    level: ReviewerLevel = ReviewerLevel.blocking,
    languages: list[str] | None = None,
) -> ReviewerConfig:
    """Create a ReviewerConfig for testing."""
    return ReviewerConfig(name=name, skill=skill, level=level, languages=languages)


def _setup_loop_project(tmp_path: Path, reviewer_names: list[str]) -> None:
    """Set up a project structure for testing _run_review_loop."""
    (tmp_path / "plans").mkdir(exist_ok=True)
    (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")

    # Build CLAUDE.md with reviewer config
    reviewer_yaml_lines = []
    for name in reviewer_names:
        reviewer_yaml_lines.append(f"  - name: {name}")
        reviewer_yaml_lines.append(f"    skill: reviewers/{name}")
        reviewer_yaml_lines.append("    level: blocking")

    reviewer_yaml = "\n".join(reviewer_yaml_lines)
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        f"""# Project

<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
{reviewer_yaml}
```
<!-- RALPH:REVIEWERS:END -->
"""
    )
