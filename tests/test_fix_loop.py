"""Tests for fix loop execution service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph.models.finding import Finding
from ralph.services.fix_loop import FixLoopService, FixResult


class TestFixLoopServiceAttemptFix:
    """Tests for single fix attempt logic."""

    @patch("ralph.services.fix_loop.ClaudeService")
    def test_success_returns_true(self, mock_claude_class: MagicMock, tmp_path: Path) -> None:
        """Test attempt_fix returns True on success."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Fix applied", 0)
        mock_claude_class.return_value = mock_claude

        service = _create_service(tmp_path)
        finding = _create_finding()

        success, error = service.attempt_fix(finding)

        assert success is True
        assert error is None
        mock_claude.run_print_mode.assert_called_once()

    @patch("ralph.services.fix_loop.ClaudeService")
    def test_failure_returns_false_with_error(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test attempt_fix returns False with error on failure."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Failed", 1)
        mock_claude_class.return_value = mock_claude

        service = _create_service(tmp_path)
        finding = _create_finding()

        success, error = service.attempt_fix(finding)

        assert success is False
        assert error is not None
        assert "exit" in error.lower()

    @patch("ralph.services.fix_loop.ClaudeService")
    def test_exception_returns_false_with_error(
        self, mock_claude_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test attempt_fix returns False with error on exception."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = Exception("Connection failed")
        mock_claude_class.return_value = mock_claude

        service = _create_service(tmp_path)
        finding = _create_finding()

        success, error = service.attempt_fix(finding)

        assert success is False
        assert "Connection failed" in error


class TestFixLoopServiceRunFixLoop:
    """Tests for running the full fix loop with retry logic."""

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_success_on_first_attempt(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop succeeds on first attempt."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Fix applied", 0)
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.return_value = "abc1234"
        mock_git_class.return_value = mock_git

        service = _create_service(tmp_path)
        findings = [_create_finding()]

        results = service.run_fix_loop(findings)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].attempts == 1
        assert results[0].finding_id == "FINDING-001"

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_retries_on_failure(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop retries up to max_retries on failure."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = [
            ("Fail", 1),
            ("Fail", 1),
            ("Success", 0),
        ]
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.return_value = "abc1234"
        mock_git_class.return_value = mock_git

        service = _create_service(tmp_path, max_retries=3)
        findings = [_create_finding()]

        results = service.run_fix_loop(findings)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].attempts == 3

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_exhausted_retries_continues(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop continues after exhausting retries for a finding."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.side_effect = [
            ("Fail", 1),
            ("Fail", 1),
            ("Fail", 1),  # First finding exhausts retries
            ("Success", 0),  # Second finding succeeds
        ]
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.return_value = "abc1234"
        mock_git_class.return_value = mock_git

        service = _create_service(tmp_path, max_retries=3)
        findings = [
            _create_finding(finding_id="FINDING-001"),
            _create_finding(finding_id="FINDING-002"),
        ]

        results = service.run_fix_loop(findings)

        assert len(results) == 2
        assert results[0].success is False
        assert results[0].attempts == 3
        assert results[0].error is not None
        assert results[1].success is True
        assert results[1].attempts == 1

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_logs_success_to_progress(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop logs successful fixes to PROGRESS.txt."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Fix applied", 0)
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.return_value = "abc1234"
        mock_git_class.return_value = mock_git

        progress_path = tmp_path / "PROGRESS.txt"
        progress_path.write_text("# Progress\n")

        service = _create_service(tmp_path)
        findings = [_create_finding()]

        service.run_fix_loop(findings, progress_path=progress_path)

        content = progress_path.read_text()
        assert "[Review Fix]" in content
        assert "test-reviewer/FINDING-001" in content
        assert "What was fixed" in content

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_logs_failure_to_progress(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop logs failed fixes to PROGRESS.txt."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Failed", 1)
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git_class.return_value = mock_git

        progress_path = tmp_path / "PROGRESS.txt"
        progress_path.write_text("# Progress\n")

        service = _create_service(tmp_path, max_retries=2)
        findings = [_create_finding()]

        service.run_fix_loop(findings, progress_path=progress_path)

        content = progress_path.read_text()
        assert "[Review Fix Failed]" in content
        assert "test-reviewer/FINDING-001" in content
        assert "exhausted" in content

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_calls_on_fix_step_callback(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fix loop calls on_fix_step callback for each finding."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Fix applied", 0)
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.return_value = "abc1234"
        mock_git_class.return_value = mock_git

        service = _create_service(tmp_path)
        findings = [
            _create_finding(finding_id="FINDING-001"),
            _create_finding(finding_id="FINDING-002"),
        ]

        callback = MagicMock()
        service.run_fix_loop(findings, on_fix_step=callback)

        assert callback.call_count == 2
        callback.assert_any_call(1, 2, "FINDING-001")
        callback.assert_any_call(2, 2, "FINDING-002")


class TestFixLoopServiceCommitFix:
    """Tests for fix commit creation."""

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_commit_format_matches_spec(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test commit message format: fix(review): [reviewer] - [finding-id] - [description]."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Fix applied", 0)
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.return_value = "abc1234"
        mock_git_class.return_value = mock_git

        service = _create_service(tmp_path, reviewer_name="python-code")
        findings = [_create_finding(issue="Missing type hint")]

        service.run_fix_loop(findings)

        mock_git.commit.assert_called_once()
        commit_msg = mock_git.commit.call_args[0][0]
        assert commit_msg.startswith("fix(review): python-code - FINDING-001")
        assert "Missing type hint" in commit_msg

    @patch("ralph.services.fix_loop.GitService")
    @patch("ralph.services.fix_loop.ClaudeService")
    def test_no_commit_when_no_changes(
        self,
        mock_claude_class: MagicMock,
        mock_git_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no commit is made when there are no changes."""
        mock_claude = MagicMock()
        mock_claude.run_print_mode.return_value = ("Fix applied", 0)
        mock_claude_class.return_value = mock_claude

        mock_git = MagicMock()
        mock_git.has_changes.return_value = False
        mock_git_class.return_value = mock_git

        service = _create_service(tmp_path)
        findings = [_create_finding()]

        service.run_fix_loop(findings)

        mock_git.commit.assert_not_called()


class TestFixResult:
    """Tests for FixResult data structure."""

    def test_fix_result_creation(self) -> None:
        """Test FixResult can be created with all fields."""
        result = FixResult(
            finding_id="FINDING-001",
            success=True,
            attempts=2,
            error=None,
        )

        assert result.finding_id == "FINDING-001"
        assert result.success is True
        assert result.attempts == 2
        assert result.error is None

    def test_fix_result_with_error(self) -> None:
        """Test FixResult with error field."""
        result = FixResult(
            finding_id="FINDING-001",
            success=False,
            attempts=3,
            error="Claude exited with code 1",
        )

        assert result.success is False
        assert result.error == "Claude exited with code 1"


class TestBuildFixPrompt:
    """Tests for fix prompt construction."""

    def test_prompt_includes_finding_details(self, tmp_path: Path) -> None:
        """Test fix prompt includes all finding details."""
        service = _create_service(tmp_path)
        finding = _create_finding(
            finding_id="FINDING-042",
            category="Type Safety",
            file_path="src/module.py",
            line_number=42,
            issue="Missing type annotation",
            suggestion="Add type hint",
        )

        prompt = service._build_fix_prompt(finding)

        assert "FINDING-042" in prompt
        assert "Type Safety" in prompt
        assert "src/module.py" in prompt
        assert "line 42" in prompt
        assert "Missing type annotation" in prompt
        assert "Add type hint" in prompt

    def test_prompt_handles_no_line_number(self, tmp_path: Path) -> None:
        """Test fix prompt handles missing line number."""
        service = _create_service(tmp_path)
        finding = _create_finding(line_number=None)

        prompt = service._build_fix_prompt(finding)

        assert "line" not in prompt.lower() or "at line" not in prompt


def _create_service(
    tmp_path: Path,
    reviewer_name: str = "test-reviewer",
    max_retries: int = 3,
) -> FixLoopService:
    """Create a FixLoopService for testing."""
    return FixLoopService(
        project_root=tmp_path,
        reviewer_name=reviewer_name,
        max_retries=max_retries,
    )


def _create_finding(
    finding_id: str = "FINDING-001",
    category: str = "Test Category",
    file_path: str = "src/test.py",
    line_number: int | None = 10,
    issue: str = "Test issue description",
    suggestion: str = "Test suggestion",
) -> Finding:
    """Create a Finding for testing."""
    return Finding(
        id=finding_id,
        category=category,
        file_path=file_path,
        line_number=line_number,
        issue=issue,
        suggestion=suggestion,
    )
