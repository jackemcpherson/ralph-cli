"""Tests for review loop execution service."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph.models import ReviewerConfig, ReviewerLevel
from ralph.models.finding import Verdict
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

    @patch("ralph.services.review_loop.ClaudeService")
    def test_parses_structured_output_on_success(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test run_reviewer parses structured output when reviewer succeeds."""
        structured_output = """
### Verdict: PASSED

No issues found.
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer()

        result = service.run_reviewer(reviewer)

        assert result.success
        assert result.review_output is not None
        assert result.review_output.verdict == Verdict.PASSED
        assert result.review_output.findings == []

    @patch("ralph.services.review_loop.ClaudeService")
    def test_parses_findings_from_output(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test run_reviewer parses findings from structured output."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing return type annotation
   - File: src/service.py:42
   - Issue: Function lacks return type annotation
   - Suggestion: Add -> None return type
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer()

        result = service.run_reviewer(reviewer)

        assert result.success
        assert result.review_output is not None
        assert result.review_output.verdict == Verdict.NEEDS_WORK
        assert len(result.review_output.findings) == 1
        assert result.review_output.findings[0].id == "FINDING-001"
        assert result.review_output.findings[0].file_path == "src/service.py"
        assert result.review_output.findings[0].line_number == 42

    @patch("ralph.services.review_loop.ClaudeService")
    def test_includes_review_output_on_failure(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test run_reviewer includes review_output even when reviewer fails."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Code Style - Formatting issue
   - File: src/module.py:10
   - Issue: Line too long
   - Suggestion: Break into multiple lines
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 1)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer()

        result = service.run_reviewer(reviewer, enforced=False)

        assert not result.success
        assert result.review_output is not None
        assert result.review_output.verdict == Verdict.NEEDS_WORK
        assert len(result.review_output.findings) == 1


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


class TestAppendReviewSummary:
    """Tests for _append_review_summary logging."""

    def test_logs_structured_format_with_findings(self, tmp_path: Path) -> None:
        """Test _append_review_summary logs structured format when findings exist."""
        from ralph.models.finding import Finding, ReviewOutput, Verdict
        from ralph.services.review_loop import ReviewerResult

        progress_file = tmp_path / "PROGRESS.txt"
        progress_file.write_text("# Progress\n")

        service = _create_service(tmp_path)
        reviewer = _create_reviewer(name="test-reviewer", level=ReviewerLevel.blocking)

        review_output = ReviewOutput(
            verdict=Verdict.NEEDS_WORK,
            findings=[
                Finding(
                    id="FINDING-001",
                    category="Type Safety",
                    file_path="src/test.py",
                    line_number=42,
                    issue="Missing type annotation",
                    suggestion="Add type hint",
                )
            ],
        )
        result = ReviewerResult(
            reviewer_name="test-reviewer",
            success=True,
            skipped=False,
            attempts=1,
            review_output=review_output,
        )

        service._append_review_summary(progress_file, reviewer, result)

        content = progress_file.read_text()
        assert "[Review]" in content
        assert "test-reviewer (blocking)" in content
        assert "### Verdict: NEEDS_WORK" in content
        assert "### Findings" in content
        assert "**FINDING-001**" in content
        assert "Type Safety" in content
        assert "src/test.py:42" in content
        assert "---" in content

    def test_logs_structured_format_passed(self, tmp_path: Path) -> None:
        """Test _append_review_summary logs structured format for PASSED verdict."""
        from ralph.models.finding import ReviewOutput, Verdict
        from ralph.services.review_loop import ReviewerResult

        progress_file = tmp_path / "PROGRESS.txt"
        progress_file.write_text("# Progress\n")

        service = _create_service(tmp_path)
        reviewer = _create_reviewer(name="test-reviewer", level=ReviewerLevel.blocking)

        review_output = ReviewOutput(verdict=Verdict.PASSED, findings=[])
        result = ReviewerResult(
            reviewer_name="test-reviewer",
            success=True,
            skipped=False,
            attempts=1,
            review_output=review_output,
        )

        service._append_review_summary(progress_file, reviewer, result)

        content = progress_file.read_text()
        assert "[Review]" in content
        assert "### Verdict: PASSED" in content
        assert "### Findings" not in content

    def test_logs_simple_format_when_no_review_output(self, tmp_path: Path) -> None:
        """Test _append_review_summary uses simple format when review_output is None."""
        from ralph.services.review_loop import ReviewerResult

        progress_file = tmp_path / "PROGRESS.txt"
        progress_file.write_text("# Progress\n")

        service = _create_service(tmp_path)
        reviewer = _create_reviewer(name="test-reviewer", level=ReviewerLevel.warning)

        result = ReviewerResult(
            reviewer_name="test-reviewer",
            success=True,
            skipped=False,
            attempts=1,
            review_output=None,
        )

        service._append_review_summary(progress_file, reviewer, result)

        content = progress_file.read_text()
        assert "[Review Loop]" in content
        assert "passed" in content

    def test_logs_skipped_format(self, tmp_path: Path) -> None:
        """Test _append_review_summary logs skipped format correctly."""
        from ralph.services.review_loop import ReviewerResult

        progress_file = tmp_path / "PROGRESS.txt"
        progress_file.write_text("# Progress\n")

        service = _create_service(tmp_path)
        reviewer = _create_reviewer(name="python-code", level=ReviewerLevel.blocking)

        result = ReviewerResult(
            reviewer_name="python-code",
            success=True,
            skipped=True,
            attempts=0,
            review_output=None,
        )

        service._append_review_summary(progress_file, reviewer, result)

        content = progress_file.read_text()
        assert "[Review Loop]" in content
        assert "skipped (language filter)" in content


class TestShouldRunFixLoop:
    """Tests for should_run_fix_loop method."""

    def test_blocking_reviewer_always_gets_fix_loop(self, tmp_path: Path) -> None:
        """Test blocking reviewers always get fix loop."""
        service = _create_service(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        assert service.should_run_fix_loop(reviewer, strict=False, was_language_filtered=False)
        assert service.should_run_fix_loop(reviewer, strict=True, was_language_filtered=False)

    def test_warning_reviewer_gets_fix_loop_only_in_strict_mode(self, tmp_path: Path) -> None:
        """Test warning reviewers only get fix loop in strict mode."""
        service = _create_service(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.warning)

        assert not service.should_run_fix_loop(reviewer, strict=False, was_language_filtered=False)
        assert service.should_run_fix_loop(reviewer, strict=True, was_language_filtered=False)

    def test_suggestion_reviewer_gets_fix_loop_only_in_strict_mode(self, tmp_path: Path) -> None:
        """Test suggestion reviewers only get fix loop in strict mode."""
        service = _create_service(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.suggestion)

        assert not service.should_run_fix_loop(reviewer, strict=False, was_language_filtered=False)
        assert service.should_run_fix_loop(reviewer, strict=True, was_language_filtered=False)

    def test_language_filtered_reviewer_skips_fix_loop(self, tmp_path: Path) -> None:
        """Test language-filtered reviewers skip fix loop."""
        service = _create_service(tmp_path)

        # Even blocking reviewers skip fix loop if language-filtered
        blocking = _create_reviewer(level=ReviewerLevel.blocking)
        assert not service.should_run_fix_loop(blocking, strict=True, was_language_filtered=True)


class TestRunReviewLoopWithFixLoop:
    """Tests for fix loop integration in run_review_loop."""

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_runs_fix_loop_on_needs_work_blocking(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop runs when blocking reviewer returns NEEDS_WORK."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        mock_fix_service = MagicMock()
        mock_fix_service.run_fix_loop.return_value = []
        mock_fix_service_class.return_value = mock_fix_service

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        service.run_review_loop([reviewer], {Language.python})

        mock_fix_service_class.assert_called_once()
        mock_fix_service.run_fix_loop.assert_called_once()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_skips_fix_loop_on_needs_work_warning_not_strict(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop skipped for warning reviewer when not strict."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Style - Naming issue
   - File: src/test.py:10
   - Issue: Bad name
   - Suggestion: Better name
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.warning)

        service.run_review_loop([reviewer], {Language.python}, strict=False)

        mock_fix_service_class.assert_not_called()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_runs_fix_loop_on_needs_work_warning_strict(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop runs for warning reviewer when strict=True."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Style - Naming issue
   - File: src/test.py:10
   - Issue: Bad name
   - Suggestion: Better name
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        mock_fix_service = MagicMock()
        mock_fix_service.run_fix_loop.return_value = []
        mock_fix_service_class.return_value = mock_fix_service

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.warning)

        service.run_review_loop([reviewer], {Language.python}, strict=True)

        mock_fix_service_class.assert_called_once()
        mock_fix_service.run_fix_loop.assert_called_once()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_skips_fix_loop_on_passed_verdict(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop skipped when reviewer returns PASSED."""
        structured_output = """
### Verdict: PASSED

No issues found.
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        service.run_review_loop([reviewer], {Language.python})

        mock_fix_service_class.assert_not_called()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_skips_fix_loop_on_needs_work(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix=True skips fix loop when reviewer returns NEEDS_WORK."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        results = service.run_review_loop([reviewer], {Language.python}, no_fix=True)

        mock_fix_service_class.assert_not_called()
        assert len(results) == 1

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_logs_skip_message(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test no_fix=True logs '[Fix] Skipped (--no-fix)' message."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        with caplog.at_level(logging.INFO):
            service.run_review_loop([reviewer], {Language.python}, no_fix=True)

        assert any("[Fix] Skipped (--no-fix)" in record.message for record in caplog.records)

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_continues_to_next_reviewer(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix=True continues processing remaining reviewers."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        passed_output = """
### Verdict: PASSED

No issues found.
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = [
            (structured_output, 0),
            (passed_output, 0),
        ]
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skills(tmp_path, ["test-quality", "code-simplifier"])
        reviewers = [
            _create_reviewer(name="test-quality", skill="reviewers/test-quality"),
            _create_reviewer(name="code-simplifier", skill="reviewers/code-simplifier"),
        ]

        results = service.run_review_loop(reviewers, {Language.python}, no_fix=True)

        # Both reviewers should have run
        assert len(results) == 2
        assert results[0].reviewer_name == "test-quality"
        assert results[1].reviewer_name == "code-simplifier"
        # Fix loop should not have been called
        mock_fix_service_class.assert_not_called()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_false_still_runs_fix_loop(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix=False (default) still runs fix loop normally."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        mock_fix_service = MagicMock()
        mock_fix_service.run_fix_loop.return_value = []
        mock_fix_service_class.return_value = mock_fix_service

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        service.run_review_loop([reviewer], {Language.python}, no_fix=False)

        mock_fix_service_class.assert_called_once()
        mock_fix_service.run_fix_loop.assert_called_once()

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_calls_on_fix_step_callback(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test on_fix_step callback is passed to fix loop."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        mock_fix_service = MagicMock()
        mock_fix_service.run_fix_loop.return_value = []
        mock_fix_service_class.return_value = mock_fix_service

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        callback = MagicMock()
        service.run_review_loop([reviewer], {Language.python}, on_fix_step=callback)

        # Verify callback was passed to run_fix_loop
        mock_fix_service.run_fix_loop.assert_called_once()
        call_kwargs = mock_fix_service.run_fix_loop.call_args.kwargs
        assert call_kwargs.get("on_fix_step") == callback


class TestNoFixSummary:
    """Tests for --no-fix summary output in review results."""

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_sets_fix_skipped_on_needs_work_result(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix=True sets fix_skipped=True on NEEDS_WORK results."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        results = service.run_review_loop([reviewer], {Language.python}, no_fix=True)

        assert len(results) == 1
        assert results[0].fix_skipped is True

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_does_not_set_fix_skipped_on_passed_result(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix=True does not set fix_skipped on PASSED results."""
        passed_output = """
### Verdict: PASSED

No issues found.
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (passed_output, 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        results = service.run_review_loop([reviewer], {Language.python}, no_fix=True)

        assert len(results) == 1
        assert results[0].fix_skipped is False

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_false_does_not_set_fix_skipped(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix=False (default) does not set fix_skipped."""
        structured_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = (structured_output, 0)
        mock_claude_class.return_value = mock_claude

        mock_fix_service = MagicMock()
        mock_fix_service.run_fix_loop.return_value = []
        mock_fix_service_class.return_value = mock_fix_service

        service = _create_service_with_skill(tmp_path)
        reviewer = _create_reviewer(level=ReviewerLevel.blocking)

        results = service.run_review_loop([reviewer], {Language.python}, no_fix=False)

        assert len(results) == 1
        assert results[0].fix_skipped is False

    @patch("ralph.services.review_loop.FixLoopService")
    @patch("ralph.services.review_loop.ClaudeService")
    def test_no_fix_mixed_results_only_marks_needs_work(
        self,
        mock_claude_class: MagicMock,
        mock_fix_service_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no_fix only marks fix_skipped on NEEDS_WORK reviewers, not PASSED ones."""
        needs_work_output = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing type
   - File: src/test.py:10
   - Issue: Missing type annotation
   - Suggestion: Add type hint
"""
        passed_output = """
### Verdict: PASSED

No issues found.
"""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = [
            (needs_work_output, 0),
            (passed_output, 0),
        ]
        mock_claude_class.return_value = mock_claude

        service = _create_service_with_skills(tmp_path, ["test-quality", "code-simplifier"])
        reviewers = [
            _create_reviewer(name="test-quality", skill="reviewers/test-quality"),
            _create_reviewer(name="code-simplifier", skill="reviewers/code-simplifier"),
        ]

        results = service.run_review_loop(reviewers, {Language.python}, no_fix=True)

        assert len(results) == 2
        assert results[0].fix_skipped is True
        assert results[0].reviewer_name == "test-quality"
        assert results[1].fix_skipped is False
        assert results[1].reviewer_name == "code-simplifier"


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
