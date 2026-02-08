"""Integration tests for ralph review command."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ralph.cli import app
from ralph.models import REVIEW_STATE_FILENAME, ReviewState
from ralph.models.finding import Finding, ReviewOutput, Verdict
from ralph.models.reviewer import ReviewerConfig, ReviewerLevel
from ralph.services.review_loop import ReviewerResult


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


def _setup_tmp_project(tmp_path: Path) -> None:
    """Create minimal project structure for review command tests."""
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "PROGRESS.txt").write_text("# Progress\n")


class TestReviewFirstRun:
    """Tests for first-run behavior when no reviewer config exists."""

    def test_first_run_detects_and_writes_config(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that first run detects reviewers and writes CLAUDE.md config."""
        _setup_tmp_project(tmp_path)
        detected = _make_reviewers(["code-simplifier", "repo-structure", "python-code"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=False),
                patch("ralph.commands.review.detect_reviewers", return_value=detected),
                patch("ralph.commands.review.write_reviewer_config") as mock_write,
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert result.exit_code == 0
        assert "First run detected" in result.output
        mock_write.assert_called_once()
        written_reviewers = mock_write.call_args[0][1]
        assert len(written_reviewers) == 3

    def test_first_run_displays_detected_reviewers(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that first run displays which reviewers were detected with reasons."""
        _setup_tmp_project(tmp_path)
        detected = _make_reviewers(["code-simplifier", "python-code"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=False),
                patch("ralph.commands.review.detect_reviewers", return_value=detected),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert "Detected Reviewers" in result.output
        assert "code-simplifier" in result.output
        assert "python-code" in result.output

    def test_first_run_executes_review_loop(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that first run executes the review loop after writing config."""
        _setup_tmp_project(tmp_path)
        detected = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=False),
                patch("ralph.commands.review.detect_reviewers", return_value=detected),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
                patch("ralph.commands.review.detect_languages", return_value=set()),
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review"])

        assert result.exit_code == 0
        mock_service.run_reviewer.assert_called_once()
        assert "Review Summary" in result.output


class TestReviewSubsequentRun:
    """Tests for subsequent-run behavior when config already exists."""

    def test_subsequent_run_uses_existing_config(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that subsequent runs use existing config from CLAUDE.md."""
        _setup_tmp_project(tmp_path)
        existing = _make_reviewers(["code-simplifier", "repo-structure"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=existing),
                patch("ralph.commands.review.detect_reviewers", return_value=existing),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review"])

        assert "Using existing reviewer configuration" in result.output
        assert result.exit_code == 0

    def test_subsequent_run_suggests_missing_reviewers(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that subsequent runs warn about reviewers not in config."""
        _setup_tmp_project(tmp_path)
        existing = _make_reviewers(["code-simplifier"])
        detected = _make_reviewers(["code-simplifier", "python-code", "test-quality"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=existing),
                patch("ralph.commands.review.detect_reviewers", return_value=detected),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert "Suggested reviewers not in current config" in result.output
        assert "python-code" in result.output
        assert "test-quality" in result.output
        assert "ralph review --force" in result.output

    def test_subsequent_run_no_suggestions_when_config_complete(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that no suggestions shown when config covers all detected reviewers."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier", "repo-structure"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert "Suggested reviewers not in current config" not in result.output
        assert "ralph review --force" not in result.output


class TestReviewForceFlag:
    """Tests for --force flag updating existing configuration."""

    def test_force_updates_existing_config(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --force re-detects and overwrites existing config."""
        _setup_tmp_project(tmp_path)
        old = _make_reviewers(["code-simplifier"])
        new = _make_reviewers(["code-simplifier", "python-code"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=old),
                patch("ralph.commands.review.detect_reviewers", return_value=new),
                patch("ralph.commands.review.write_reviewer_config") as mock_write,
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review", "--force"])

        assert result.exit_code == 0
        assert "Force mode" in result.output
        assert "Configuration updated" in result.output
        mock_write.assert_called_once()

    def test_force_displays_configuration_changes(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --force shows added and removed reviewers."""
        _setup_tmp_project(tmp_path)
        old = _make_reviewers(["code-simplifier", "bicep"])
        new = _make_reviewers(["code-simplifier", "python-code"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=old),
                patch("ralph.commands.review.detect_reviewers", return_value=new),
                patch("ralph.commands.review.write_reviewer_config"),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review", "--force"])

        assert "Configuration Changes" in result.output
        assert "python-code" in result.output
        assert "bicep" in result.output

    def test_force_with_no_existing_config_falls_back_to_first_run(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that --force with no existing config acts as first run."""
        _setup_tmp_project(tmp_path)
        detected = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=False),
                patch("ralph.commands.review.detect_reviewers", return_value=detected),
                patch("ralph.commands.review.write_reviewer_config") as mock_write,
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review", "--force"])

        assert "First run detected" in result.output
        mock_write.assert_called_once()


class TestReviewStrictFlag:
    """Tests for --strict flag pass-through to review loop."""

    def test_strict_flag_displayed_in_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --strict flag is acknowledged in output."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review", "--strict"])

        assert "Strict mode" in result.output

    def test_strict_flag_passed_to_is_enforced(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that --strict causes is_enforced to be called with strict=True."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                runner.invoke(app, ["review", "--strict"])

        mock_service.is_enforced.assert_called_once()
        call_args = mock_service.is_enforced.call_args
        assert call_args[1].get("strict") is True or (
            len(call_args[0]) >= 2 and call_args[0][1] is True
        )

    def test_without_strict_flag_is_not_enforced(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that without --strict, is_enforced is called with strict=False."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                runner.invoke(app, ["review"])

        mock_service.is_enforced.assert_called_once()
        call_args = mock_service.is_enforced.call_args
        assert call_args[1].get("strict") is False or (
            len(call_args[0]) >= 2 and call_args[0][1] is False
        )


class TestReviewNoFixSummary:
    """Tests for --no-fix summary output in review command."""

    def test_no_fix_shows_findings_not_fixed_in_summary(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test --no-fix shows 'findings (not fixed)' for NEEDS_WORK reviewers."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality"])

        needs_work_output = ReviewOutput(
            verdict=Verdict.NEEDS_WORK,
            findings=[
                Finding(
                    id="FINDING-001",
                    category="Type Safety",
                    file_path="src/test.py",
                    line_number=10,
                    issue="Missing type",
                    suggestion="Add type hint",
                )
            ],
        )
        needs_work_result = ReviewerResult(
            reviewer_name="test-quality",
            success=True,
            skipped=False,
            attempts=1,
            review_output=needs_work_output,
        )

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.should_run_fix_loop.return_value = True
                mock_service.run_reviewer.return_value = needs_work_result
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--no-fix"])

        assert "findings (not fixed)" in result.output
        assert "test-quality" in result.output

    def test_no_fix_includes_skipped_fix_count_in_summary_line(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test --no-fix includes 'Findings (not fixed)' count in summary line."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])

        needs_work_output = ReviewOutput(
            verdict=Verdict.NEEDS_WORK,
            findings=[
                Finding(
                    id="FINDING-001",
                    category="Type Safety",
                    file_path="src/test.py",
                    line_number=10,
                    issue="Missing type",
                    suggestion="Add type hint",
                )
            ],
        )
        needs_work_result = ReviewerResult(
            reviewer_name="test-quality",
            success=True,
            skipped=False,
            attempts=1,
            review_output=needs_work_output,
        )
        passed_result = ReviewerResult(
            reviewer_name="code-simplifier",
            success=True,
            skipped=False,
            attempts=1,
            review_output=ReviewOutput(verdict=Verdict.PASSED, findings=[]),
        )

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = MagicMock()
                mock_service.should_run_reviewer.return_value = True
                mock_service.is_enforced.return_value = True
                mock_service.should_run_fix_loop.return_value = True
                mock_service.run_reviewer.side_effect = [
                    needs_work_result,
                    passed_result,
                ]
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--no-fix"])

        assert "Findings (not fixed): 1" in result.output
        assert "Passed: 1" in result.output

    def test_no_fix_not_set_does_not_show_findings_not_fixed(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test summary without --no-fix does not show 'findings (not fixed)'."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert "findings (not fixed)" not in result.output
        assert "Findings (not fixed)" not in result.output


class TestReviewResumeReview:
    """Tests for --resume-review flag in review command."""

    def test_resume_review_skips_completed_reviewers(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test --resume-review skips already-completed reviewers from state file."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])
        config_hash = ReviewState.compute_config_hash(reviewers)

        # Write state file indicating test-quality already completed
        state = ReviewState(
            reviewer_names=["test-quality", "code-simplifier"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash=config_hash,
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        # Only code-simplifier should have been run (test-quality was resumed)
        assert mock_service.run_reviewer.call_count == 1

    def test_resume_review_runs_full_pipeline_without_state_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test --resume-review runs full pipeline when no state file exists."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        # Both reviewers should run
        assert mock_service.run_reviewer.call_count == 2

    def test_resume_review_saves_state_after_each_reviewer(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test --resume-review saves state after each reviewer, cleaned up on success."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])

        saved_states: list[ReviewState] = []
        original_save = ReviewState.save

        def tracking_save(self_state: ReviewState, path: Path) -> None:
            saved_states.append(self_state.model_copy())
            original_save(self_state, path)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
                patch.object(ReviewState, "save", tracking_save),
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        # State was saved after each reviewer (2 saves for 2 reviewers)
        assert len(saved_states) == 2
        assert "test-quality" in saved_states[0].completed
        assert "test-quality" in saved_states[1].completed
        assert "code-simplifier" in saved_states[1].completed

    def test_resume_review_config_hash_mismatch_runs_full_pipeline(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test --resume-review discards state when config hash doesn't match."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])

        # Write state file with a different config hash
        state = ReviewState(
            reviewer_names=["test-quality", "code-simplifier"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="stale_hash_that_does_not_match",
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        # Both reviewers should run since hash didn't match
        assert mock_service.run_reviewer.call_count == 2


class TestReviewStateCleanup:
    """Tests for state file cleanup on successful completion."""

    def test_state_file_cleaned_up_on_successful_completion(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that .ralph-review-state.json is deleted when all reviewers pass."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])
        config_hash = ReviewState.compute_config_hash(reviewers)

        # Create a state file as if from a previous resume
        state = ReviewState(
            reviewer_names=["test-quality", "code-simplifier"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash=config_hash,
        )
        state_path = tmp_path / REVIEW_STATE_FILENAME
        state.save(state_path)
        assert state_path.exists()

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        # State file should be cleaned up after successful completion
        assert not state_path.exists()

    def test_state_file_cleaned_up_without_resume_flag(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test cleanup happens even without --resume-review if state file exists."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier"])

        # Create a leftover state file
        state = ReviewState(
            reviewer_names=["code-simplifier"],
            completed={},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="some_hash",
        )
        state_path = tmp_path / REVIEW_STATE_FILENAME
        state.save(state_path)
        assert state_path.exists()

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert result.exit_code == 0
        # State file should be cleaned up even without --resume-review
        assert not state_path.exists()

    def test_no_error_when_no_state_file_to_clean(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that cleanup doesn't error when no state file exists."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["code-simplifier"])
        state_path = tmp_path / REVIEW_STATE_FILENAME
        assert not state_path.exists()

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review"])

        assert result.exit_code == 0


class TestReviewConfigInvalidation:
    """Tests for config change invalidation of stale state."""

    def test_config_change_logs_discard_message(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that a console message is shown when state is discarded due to config change."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])

        # Write state file with a stale config hash
        state = ReviewState(
            reviewer_names=["test-quality", "code-simplifier"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="stale_hash_that_does_not_match",
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_cls.return_value = _make_mock_service()
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        assert "reviewer configuration has changed" in result.output

    def test_config_change_runs_all_reviewers_from_scratch(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that config change causes all reviewers to run, ignoring stale completed state."""
        _setup_tmp_project(tmp_path)
        reviewers = _make_reviewers(["test-quality", "code-simplifier"])

        # Write state file with stale hash where test-quality was already completed
        state = ReviewState(
            reviewer_names=["test-quality", "code-simplifier"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="stale_hash",
        )
        state.save(tmp_path / REVIEW_STATE_FILENAME)

        with working_directory(tmp_path):
            with (
                patch("ralph.commands.review.has_reviewer_config", return_value=True),
                patch("ralph.commands.review.load_reviewer_configs", return_value=reviewers),
                patch("ralph.commands.review.detect_reviewers", return_value=reviewers),
                patch("ralph.commands.review.detect_languages", return_value=set()),
                patch("ralph.commands.review.ReviewLoopService") as mock_cls,
            ):
                mock_service = _make_mock_service()
                mock_cls.return_value = mock_service
                result = runner.invoke(app, ["review", "--resume-review"])

        assert result.exit_code == 0
        # Both reviewers should run since config hash didn't match
        assert mock_service.run_reviewer.call_count == 2
