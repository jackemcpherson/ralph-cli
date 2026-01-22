"""Tests for review loop execution service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph.models import ReviewerConfig, ReviewerLevel
from ralph.services import Language, ReviewLoopService, filter_reviewers_by_language


class TestReviewLoopServiceShouldRunReviewer:
    """Tests for reviewer language filtering logic."""

    def test_reviewer_without_language_filter_always_runs(self, tmp_path: Path) -> None:
        """Test reviewers without language filter run for any project."""
        service = _create_service(tmp_path)
        reviewer = _create_reviewer(languages=None)

        assert service.should_run_reviewer(reviewer, set())
        assert service.should_run_reviewer(reviewer, {Language.python})
        assert service.should_run_reviewer(reviewer, {Language.go, Language.rust})

    def test_reviewer_with_matching_language_runs(self, tmp_path: Path) -> None:
        """Test reviewers run when language matches."""
        service = _create_service(tmp_path)
        reviewer = _create_reviewer(languages=["python"])

        assert service.should_run_reviewer(reviewer, {Language.python})
        assert service.should_run_reviewer(reviewer, {Language.python, Language.go})
        assert not service.should_run_reviewer(reviewer, {Language.go})
        assert not service.should_run_reviewer(reviewer, set())


class TestReviewLoopServiceIsEnforced:
    """Tests for reviewer enforcement logic."""

    def test_enforcement_levels(self, tmp_path: Path) -> None:
        """Test enforcement rules for different reviewer levels."""
        service = _create_service(tmp_path)

        blocking = _create_reviewer(level=ReviewerLevel.blocking)
        warning = _create_reviewer(level=ReviewerLevel.warning)
        suggestion = _create_reviewer(level=ReviewerLevel.suggestion)

        assert service.is_enforced(blocking, strict=False)
        assert service.is_enforced(blocking, strict=True)

        assert not service.is_enforced(warning, strict=False)
        assert service.is_enforced(warning, strict=True)

        assert not service.is_enforced(suggestion, strict=False)
        assert not service.is_enforced(suggestion, strict=True)


class TestReviewLoopServiceRunReviewer:
    """Tests for reviewer execution with retry logic."""

    def test_skill_not_found_returns_error(self, tmp_path: Path) -> None:
        """Test run_reviewer returns error when skill not found."""
        service = _create_service(tmp_path)
        reviewer = _create_reviewer(skill="reviewers/missing")

        result = service.run_reviewer(reviewer)

        assert not result.success
        assert "Skill not found" in result.error

    @patch("ralph.services.review_loop.ClaudeService")
    def test_success_on_first_attempt(self, mock_claude_class: MagicMock, tmp_path: Path) -> None:
        """Test run_reviewer succeeds on first attempt."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Review complete", 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer()

        result = service.run_reviewer(reviewer, enforced=True)

        assert result.success
        assert result.attempts == 1

    @patch("ralph.services.review_loop.ClaudeService")
    def test_retries_when_enforced(self, mock_claude_class: MagicMock, tmp_path: Path) -> None:
        """Test run_reviewer retries up to max_retries when enforced."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = [("Fail", 1), ("Fail", 1), ("Success", 0)]
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer()

        result = service.run_reviewer(reviewer, enforced=True, max_retries=3)

        assert result.success
        assert result.attempts == 3

    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_retry_when_not_enforced(self, mock_claude_class: MagicMock, tmp_path: Path) -> None:
        """Test run_reviewer doesn't retry when not enforced."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Failed", 1)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.warning)

        result = service.run_reviewer(reviewer, enforced=False, max_retries=3)

        assert not result.success
        assert result.attempts == 1


class TestReviewLoopServiceRunReviewLoop:
    """Tests for running the full review loop."""

    @patch("ralph.services.review_loop.ClaudeService")
    def test_executes_reviewers_in_order(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test reviewers execute in configured order."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Success", 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skills(tmp_path, ["test-quality", "code-simplifier"])
        reviewers = [
            _create_reviewer(name="test-quality", skill="reviewers/test-quality"),
            _create_reviewer(name="code-simplifier", skill="reviewers/code-simplifier"),
        ]

        results = service.run_review_loop(reviewers, {Language.python})

        assert len(results) == 2
        assert results[0].reviewer_name == "test-quality"
        assert results[1].reviewer_name == "code-simplifier"
        assert all(r.success for r in results)

    @patch("ralph.services.review_loop.ClaudeService")
    def test_skips_non_matching_language(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test reviewers with non-matching language filter are skipped."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Success", 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skills(tmp_path, ["test-quality", "python-code"])
        reviewers = [
            _create_reviewer(name="test-quality", skill="reviewers/test-quality"),
            _create_reviewer(
                name="python-code", skill="reviewers/python-code", languages=["python"]
            ),
        ]

        results = service.run_review_loop(reviewers, {Language.go})

        assert results[0].skipped is False
        assert results[1].skipped is True
        assert mock_claude.run_print_mode.call_count == 1


class TestFilterReviewersByLanguage:
    """Tests for filter_reviewers_by_language function."""

    def test_filters_correctly(self) -> None:
        """Test filter_reviewers_by_language filters correctly."""
        reviewers = [
            _create_reviewer(name="universal"),
            _create_reviewer(name="python-only", languages=["python"]),
            _create_reviewer(name="go-only", languages=["go"]),
        ]

        filtered = filter_reviewers_by_language(reviewers, {Language.python})

        assert len(filtered) == 2
        assert filtered[0].name == "universal"
        assert filtered[1].name == "python-only"


def _create_service(tmp_path: Path) -> ReviewLoopService:
    """Create a ReviewLoopService for testing."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return ReviewLoopService(project_root=tmp_path, skills_dir=skills_dir)


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
