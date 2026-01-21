"""Unit tests for review loop execution service.

Focused tests for review loop functionality:
- Reviewer filtering by language
- Retry logic for blocking reviewers
- Enforcement rules for different reviewer levels
- Progress summary appending
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph.models import ReviewerConfig, ReviewerLevel
from ralph.services import Language, ReviewerResult, ReviewLoopService, filter_reviewers_by_language


class TestReviewerResult:
    """Tests for the ReviewerResult NamedTuple."""

    def test_reviewer_result_success(self) -> None:
        """Test ReviewerResult for successful execution."""
        result = ReviewerResult(
            reviewer_name="test-quality",
            success=True,
            skipped=False,
            attempts=1,
        )

        assert result.reviewer_name == "test-quality"
        assert result.success is True
        assert result.skipped is False
        assert result.attempts == 1
        assert result.error is None

    def test_reviewer_result_failure(self) -> None:
        """Test ReviewerResult for failed execution."""
        result = ReviewerResult(
            reviewer_name="code-simplifier",
            success=False,
            skipped=False,
            attempts=3,
            error="Failed after 3 attempts",
        )

        assert result.success is False
        assert result.attempts == 3
        assert result.error == "Failed after 3 attempts"

    def test_reviewer_result_skipped(self) -> None:
        """Test ReviewerResult for skipped reviewer."""
        result = ReviewerResult(
            reviewer_name="python-code",
            success=True,
            skipped=True,
            attempts=0,
        )

        assert result.success is True
        assert result.skipped is True
        assert result.attempts == 0


class TestReviewLoopServiceShouldRunReviewer:
    """Tests for should_run_reviewer method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReviewLoopService:
        """Create a ReviewLoopService instance for testing."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return ReviewLoopService(
            project_root=tmp_path,
            skills_dir=skills_dir,
        )

    def test_reviewer_without_language_filter_always_runs(self, service: ReviewLoopService) -> None:
        """Test reviewers without language filter always run."""
        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
            languages=None,
        )

        assert service.should_run_reviewer(reviewer, set()) is True
        assert service.should_run_reviewer(reviewer, {Language.python}) is True
        assert service.should_run_reviewer(reviewer, {Language.go, Language.rust}) is True

    def test_reviewer_with_empty_language_filter_always_runs(
        self, service: ReviewLoopService
    ) -> None:
        """Test reviewers with empty language list always run."""
        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
            languages=[],
        )

        assert service.should_run_reviewer(reviewer, set()) is True
        assert service.should_run_reviewer(reviewer, {Language.python}) is True

    def test_reviewer_with_matching_language_runs(self, service: ReviewLoopService) -> None:
        """Test reviewers run when language matches."""
        reviewer = ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        )

        assert service.should_run_reviewer(reviewer, {Language.python}) is True
        assert service.should_run_reviewer(reviewer, {Language.python, Language.go}) is True

    def test_reviewer_with_non_matching_language_skipped(self, service: ReviewLoopService) -> None:
        """Test reviewers skip when language doesn't match."""
        reviewer = ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        )

        assert service.should_run_reviewer(reviewer, set()) is False
        assert service.should_run_reviewer(reviewer, {Language.go}) is False
        assert service.should_run_reviewer(reviewer, {Language.rust, Language.go}) is False

    def test_reviewer_with_multiple_languages_filter(self, service: ReviewLoopService) -> None:
        """Test reviewers with multiple languages filter."""
        reviewer = ReviewerConfig(
            name="js-ts-reviewer",
            skill="reviewers/language/js-ts",
            level=ReviewerLevel.blocking,
            languages=["javascript", "typescript"],
        )

        # Matches if any language in filter matches detected
        assert service.should_run_reviewer(reviewer, {Language.javascript}) is True
        assert service.should_run_reviewer(reviewer, {Language.typescript}) is True
        assert (
            service.should_run_reviewer(reviewer, {Language.javascript, Language.typescript})
            is True
        )
        assert service.should_run_reviewer(reviewer, {Language.python}) is False


class TestReviewLoopServiceIsEnforced:
    """Tests for is_enforced method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReviewLoopService:
        """Create a ReviewLoopService instance for testing."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return ReviewLoopService(
            project_root=tmp_path,
            skills_dir=skills_dir,
        )

    def test_blocking_reviewer_always_enforced(self, service: ReviewLoopService) -> None:
        """Test blocking reviewers are always enforced."""
        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )

        assert service.is_enforced(reviewer, strict=False) is True
        assert service.is_enforced(reviewer, strict=True) is True

    def test_warning_reviewer_enforced_in_strict_mode(self, service: ReviewLoopService) -> None:
        """Test warning reviewers are enforced in strict mode."""
        reviewer = ReviewerConfig(
            name="github-actions",
            skill="reviewers/github-actions",
            level=ReviewerLevel.warning,
        )

        assert service.is_enforced(reviewer, strict=False) is False
        assert service.is_enforced(reviewer, strict=True) is True

    def test_suggestion_reviewer_never_enforced(self, service: ReviewLoopService) -> None:
        """Test suggestion reviewers are never enforced."""
        reviewer = ReviewerConfig(
            name="style-guide",
            skill="reviewers/style-guide",
            level=ReviewerLevel.suggestion,
        )

        assert service.is_enforced(reviewer, strict=False) is False
        assert service.is_enforced(reviewer, strict=True) is False


class TestReviewLoopServiceRunReviewer:
    """Tests for run_reviewer method with retry logic."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReviewLoopService:
        """Create a ReviewLoopService instance for testing."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "reviewers").mkdir()
        (skills_dir / "reviewers" / "test-quality").mkdir(parents=True)
        (skills_dir / "reviewers" / "test-quality" / "SKILL.md").write_text(
            "# Test Quality Reviewer\n\nReview test quality."
        )
        return ReviewLoopService(
            project_root=tmp_path,
            skills_dir=skills_dir,
        )

    def test_run_reviewer_skill_not_found(self, tmp_path: Path) -> None:
        """Test run_reviewer returns error when skill not found."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        service = ReviewLoopService(
            project_root=tmp_path,
            skills_dir=skills_dir,
        )

        reviewer = ReviewerConfig(
            name="missing-skill",
            skill="reviewers/missing",
            level=ReviewerLevel.blocking,
        )

        result = service.run_reviewer(reviewer)

        assert result.success is False
        assert result.skipped is False
        assert result.attempts == 0
        assert "Skill not found" in result.error

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_reviewer_success_first_attempt(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test run_reviewer succeeds on first attempt."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Review complete", 0)
        mock_claude_class.return_value = mock_claude

        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )

        result = service.run_reviewer(reviewer, enforced=True)

        assert result.success is True
        assert result.attempts == 1
        assert mock_claude.run_print_mode.call_count == 1

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_reviewer_retries_on_failure_when_enforced(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test run_reviewer retries up to 3 times when enforced."""
        mock_claude = MagicMock()
        # Fail first two attempts, succeed on third
        mock_claude.run_print_mode.side_effect = [
            ("Failed", 1),
            ("Failed", 1),
            ("Success", 0),
        ]
        mock_claude_class.return_value = mock_claude

        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )

        result = service.run_reviewer(reviewer, enforced=True, max_retries=3)

        assert result.success is True
        assert result.attempts == 3
        assert mock_claude.run_print_mode.call_count == 3

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_reviewer_no_retry_when_not_enforced(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test run_reviewer doesn't retry when not enforced."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Failed", 1)
        mock_claude_class.return_value = mock_claude

        reviewer = ReviewerConfig(
            name="github-actions",
            skill="reviewers/test-quality",  # Using existing skill path
            level=ReviewerLevel.warning,
        )

        result = service.run_reviewer(reviewer, enforced=False, max_retries=3)

        assert result.success is False
        assert result.attempts == 1
        assert mock_claude.run_print_mode.call_count == 1

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_reviewer_fails_after_max_retries(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test run_reviewer returns failure after max retries exhausted."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Failed", 1)
        mock_claude_class.return_value = mock_claude

        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )

        result = service.run_reviewer(reviewer, enforced=True, max_retries=3)

        assert result.success is False
        assert result.attempts == 3
        assert "Failed after 3 attempts" in result.error
        assert mock_claude.run_print_mode.call_count == 3

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_reviewer_handles_exception(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test run_reviewer handles exceptions gracefully."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = Exception("Connection error")
        mock_claude_class.return_value = mock_claude

        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )

        result = service.run_reviewer(reviewer, enforced=True, max_retries=3)

        assert result.success is False
        assert "Connection error" in result.error


class TestReviewLoopServiceRunReviewLoop:
    """Tests for run_review_loop method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReviewLoopService:
        """Create a ReviewLoopService instance for testing."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "reviewers" / "test-quality").mkdir(parents=True)
        (skills_dir / "reviewers" / "test-quality" / "SKILL.md").write_text(
            "# Test Quality\n\nReview tests."
        )
        (skills_dir / "reviewers" / "code-simplifier").mkdir(parents=True)
        (skills_dir / "reviewers" / "code-simplifier" / "SKILL.md").write_text(
            "# Code Simplifier\n\nSimplify code."
        )
        (skills_dir / "reviewers" / "language" / "python").mkdir(parents=True)
        (skills_dir / "reviewers" / "language" / "python" / "SKILL.md").write_text(
            "# Python Reviewer\n\nReview Python code."
        )
        return ReviewLoopService(
            project_root=tmp_path,
            skills_dir=skills_dir,
        )

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_review_loop_executes_in_order(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test reviewers execute in configured order."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Success", 0)
        mock_claude_class.return_value = mock_claude

        reviewers = [
            ReviewerConfig(
                name="test-quality",
                skill="reviewers/test-quality",
                level=ReviewerLevel.blocking,
            ),
            ReviewerConfig(
                name="code-simplifier",
                skill="reviewers/code-simplifier",
                level=ReviewerLevel.blocking,
            ),
        ]

        results = service.run_review_loop(reviewers, {Language.python})

        assert len(results) == 2
        assert results[0].reviewer_name == "test-quality"
        assert results[1].reviewer_name == "code-simplifier"
        assert all(r.success for r in results)

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_review_loop_skips_non_matching_language(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test reviewers with non-matching language filter are skipped."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Success", 0)
        mock_claude_class.return_value = mock_claude

        reviewers = [
            ReviewerConfig(
                name="test-quality",
                skill="reviewers/test-quality",
                level=ReviewerLevel.blocking,
            ),
            ReviewerConfig(
                name="python-code",
                skill="reviewers/language/python",
                level=ReviewerLevel.blocking,
                languages=["python"],
            ),
        ]

        # Only Go detected, no Python
        results = service.run_review_loop(reviewers, {Language.go})

        assert len(results) == 2
        assert results[0].reviewer_name == "test-quality"
        assert results[0].skipped is False
        assert results[1].reviewer_name == "python-code"
        assert results[1].skipped is True
        # Only first reviewer should have been called
        assert mock_claude.run_print_mode.call_count == 1

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_review_loop_appends_progress(
        self, mock_claude_class: MagicMock, service: ReviewLoopService, tmp_path: Path
    ) -> None:
        """Test review summaries are appended to PROGRESS.txt."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Success", 0)
        mock_claude_class.return_value = mock_claude

        progress_path = tmp_path / "PROGRESS.txt"
        progress_path.write_text("# Progress\n\n")

        reviewers = [
            ReviewerConfig(
                name="test-quality",
                skill="reviewers/test-quality",
                level=ReviewerLevel.blocking,
            ),
        ]

        service.run_review_loop(reviewers, {Language.python}, progress_path=progress_path)

        content = progress_path.read_text()
        assert "[Review Loop]" in content
        assert "test-quality" in content
        assert "passed" in content

    @patch("ralph.services.review_loop.ClaudeService")
    def test_run_review_loop_continues_after_failure(
        self, mock_claude_class: MagicMock, service: ReviewLoopService
    ) -> None:
        """Test loop continues to next reviewer after failure."""
        mock_claude = MagicMock()
        # First reviewer fails, second succeeds
        mock_claude.run_print_mode.side_effect = [
            ("Failed", 1),
            ("Failed", 1),
            ("Failed", 1),
            ("Success", 0),
        ]
        mock_claude_class.return_value = mock_claude

        reviewers = [
            ReviewerConfig(
                name="test-quality",
                skill="reviewers/test-quality",
                level=ReviewerLevel.blocking,
            ),
            ReviewerConfig(
                name="code-simplifier",
                skill="reviewers/code-simplifier",
                level=ReviewerLevel.blocking,
            ),
        ]

        results = service.run_review_loop(reviewers, {Language.python})

        assert len(results) == 2
        assert results[0].success is False
        assert results[0].attempts == 3
        assert results[1].success is True


class TestFilterReviewersByLanguage:
    """Tests for filter_reviewers_by_language convenience function."""

    def test_filters_reviewers_correctly(self) -> None:
        """Test filter_reviewers_by_language filters correctly."""
        reviewers = [
            ReviewerConfig(
                name="test-quality",
                skill="reviewers/test-quality",
                level=ReviewerLevel.blocking,
            ),
            ReviewerConfig(
                name="python-code",
                skill="reviewers/language/python",
                level=ReviewerLevel.blocking,
                languages=["python"],
            ),
            ReviewerConfig(
                name="go-code",
                skill="reviewers/language/go",
                level=ReviewerLevel.blocking,
                languages=["go"],
            ),
        ]

        filtered = filter_reviewers_by_language(reviewers, {Language.python})

        assert len(filtered) == 2
        assert filtered[0].name == "test-quality"
        assert filtered[1].name == "python-code"

    def test_returns_all_when_no_language_filters(self) -> None:
        """Test all reviewers returned when none have language filters."""
        reviewers = [
            ReviewerConfig(
                name="test-quality",
                skill="reviewers/test-quality",
                level=ReviewerLevel.blocking,
            ),
            ReviewerConfig(
                name="code-simplifier",
                skill="reviewers/code-simplifier",
                level=ReviewerLevel.blocking,
            ),
        ]

        filtered = filter_reviewers_by_language(reviewers, {Language.go})

        assert len(filtered) == 2

    def test_returns_empty_when_no_matches(self) -> None:
        """Test empty list returned when no reviewers match."""
        reviewers = [
            ReviewerConfig(
                name="python-code",
                skill="reviewers/language/python",
                level=ReviewerLevel.blocking,
                languages=["python"],
            ),
        ]

        filtered = filter_reviewers_by_language(reviewers, {Language.go})

        assert len(filtered) == 0


class TestReviewLoopServiceProgressSummary:
    """Tests for progress summary appending."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReviewLoopService:
        """Create a ReviewLoopService instance for testing."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return ReviewLoopService(
            project_root=tmp_path,
            skills_dir=skills_dir,
        )

    def test_append_review_summary_success(
        self, service: ReviewLoopService, tmp_path: Path
    ) -> None:
        """Test appending success summary."""
        progress_path = tmp_path / "PROGRESS.txt"
        progress_path.write_text("# Progress\n")

        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )
        result = ReviewerResult(
            reviewer_name="test-quality",
            success=True,
            skipped=False,
            attempts=1,
        )

        service._append_review_summary(progress_path, reviewer, result)

        content = progress_path.read_text()
        assert "test-quality" in content
        assert "blocking" in content
        assert "passed" in content

    def test_append_review_summary_skipped(
        self, service: ReviewLoopService, tmp_path: Path
    ) -> None:
        """Test appending skipped summary."""
        progress_path = tmp_path / "PROGRESS.txt"
        progress_path.write_text("# Progress\n")

        reviewer = ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        )
        result = ReviewerResult(
            reviewer_name="python-code",
            success=True,
            skipped=True,
            attempts=0,
        )

        service._append_review_summary(progress_path, reviewer, result)

        content = progress_path.read_text()
        assert "python-code" in content
        assert "skipped" in content
        assert "language filter" in content

    def test_append_review_summary_failure(
        self, service: ReviewLoopService, tmp_path: Path
    ) -> None:
        """Test appending failure summary."""
        progress_path = tmp_path / "PROGRESS.txt"
        progress_path.write_text("# Progress\n")

        reviewer = ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        )
        result = ReviewerResult(
            reviewer_name="test-quality",
            success=False,
            skipped=False,
            attempts=3,
            error="Timeout",
        )

        service._append_review_summary(progress_path, reviewer, result)

        content = progress_path.read_text()
        assert "test-quality" in content
        assert "failed" in content
        assert "3 attempts" in content
        assert "Timeout" in content
