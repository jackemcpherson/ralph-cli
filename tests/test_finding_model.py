"""Unit tests for Finding and ReviewOutput models.

Focused tests for finding model handling:
- Finding model creation and validation
- ReviewOutput model with verdict and findings
- parse_review_output() for extracting findings from markdown
"""

import pytest
from pydantic import ValidationError

from ralph.models import Finding, ReviewOutput, Verdict, parse_review_output


class TestFinding:
    """Tests for the Finding model."""

    def test_finding_creation_with_all_fields(self) -> None:
        """Test Finding creation with all fields."""
        finding = Finding(
            id="FINDING-001",
            category="Type Safety",
            file_path="src/ralph/models/tasks.py",
            line_number=42,
            issue="Missing type annotation",
            suggestion="Add type annotation: x: int",
        )

        assert finding.id == "FINDING-001"
        assert finding.category == "Type Safety"
        assert finding.file_path == "src/ralph/models/tasks.py"
        assert finding.line_number == 42
        assert finding.issue == "Missing type annotation"
        assert finding.suggestion == "Add type annotation: x: int"

    def test_finding_line_number_optional(self) -> None:
        """Test Finding can be created without line_number."""
        finding = Finding(
            id="FINDING-002",
            category="Documentation",
            file_path="README.md",
            issue="Missing section",
            suggestion="Add installation section",
        )

        assert finding.line_number is None

    def test_finding_requires_mandatory_fields(self) -> None:
        """Test Finding raises ValidationError for missing required fields."""
        with pytest.raises(ValidationError):
            Finding(id="FINDING-001")  # type: ignore[call-arg]


class TestVerdict:
    """Tests for the Verdict enum."""

    def test_verdict_values(self) -> None:
        """Test Verdict enum has correct values."""
        assert Verdict.PASSED.value == "PASSED"
        assert Verdict.NEEDS_WORK.value == "NEEDS_WORK"

    def test_verdict_from_string(self) -> None:
        """Test Verdict can be created from string."""
        assert Verdict("PASSED") == Verdict.PASSED
        assert Verdict("NEEDS_WORK") == Verdict.NEEDS_WORK


class TestReviewOutput:
    """Tests for the ReviewOutput model."""

    def test_review_output_passed_no_findings(self) -> None:
        """Test ReviewOutput with PASSED verdict and empty findings."""
        output = ReviewOutput(verdict=Verdict.PASSED)

        assert output.verdict == Verdict.PASSED
        assert output.findings == []

    def test_review_output_needs_work_with_findings(self) -> None:
        """Test ReviewOutput with NEEDS_WORK verdict and findings."""
        findings = [
            Finding(
                id="FINDING-001",
                category="Type Safety",
                file_path="src/app.py",
                line_number=10,
                issue="Missing type hint",
                suggestion="Add type hint",
            ),
        ]
        output = ReviewOutput(verdict=Verdict.NEEDS_WORK, findings=findings)

        assert output.verdict == Verdict.NEEDS_WORK
        assert len(output.findings) == 1
        assert output.findings[0].id == "FINDING-001"


class TestParseReviewOutput:
    """Tests for the parse_review_output() function."""

    def test_parse_passed_verdict(self) -> None:
        """Test parsing PASSED verdict with no findings."""
        text = """
[Review] 2026-01-22 10:00 UTC - test-quality (blocking)

### Verdict: PASSED

### Findings

None

---
"""
        result = parse_review_output(text)

        assert result.verdict == Verdict.PASSED
        assert result.findings == []

    def test_parse_needs_work_with_findings(self) -> None:
        """Test parsing NEEDS_WORK verdict with findings."""
        text = """
[Review] 2026-01-22 10:00 UTC - python-code (blocking)

### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Type Safety - Missing return type annotation
   - File: src/ralph/services/claude.py:42
   - Issue: Function lacks return type annotation
   - Suggestion: Add `-> str` return type annotation

2. **FINDING-002**: Code Quality - Unused import
   - File: src/ralph/utils/console.py:5
   - Issue: The import `typing` is not used
   - Suggestion: Remove the unused import

---
"""
        result = parse_review_output(text)

        assert result.verdict == Verdict.NEEDS_WORK
        assert len(result.findings) == 2

        # Check first finding
        assert result.findings[0].id == "FINDING-001"
        assert result.findings[0].category == "Type Safety"
        assert result.findings[0].file_path == "src/ralph/services/claude.py"
        assert result.findings[0].line_number == 42
        assert "return type annotation" in result.findings[0].issue
        assert "-> str" in result.findings[0].suggestion

        # Check second finding
        assert result.findings[1].id == "FINDING-002"
        assert result.findings[1].category == "Code Quality"
        assert result.findings[1].file_path == "src/ralph/utils/console.py"
        assert result.findings[1].line_number == 5

    def test_parse_no_line_number(self) -> None:
        """Test parsing finding without line number."""
        text = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Documentation - Missing docstring
   - File: src/ralph/cli.py
   - Issue: Module lacks docstring
   - Suggestion: Add a module-level docstring

---
"""
        result = parse_review_output(text)

        assert result.verdict == Verdict.NEEDS_WORK
        assert len(result.findings) == 1
        assert result.findings[0].line_number is None

    def test_parse_verdict_case_insensitive(self) -> None:
        """Test verdict parsing is case insensitive."""
        text_lower = "### Verdict: passed"
        text_mixed = "### Verdict: Needs_Work"

        result_lower = parse_review_output(text_lower)
        result_mixed = parse_review_output(text_mixed)

        assert result_lower.verdict == Verdict.PASSED
        assert result_mixed.verdict == Verdict.NEEDS_WORK

    def test_parse_no_verdict_defaults_to_passed(self) -> None:
        """Test that missing verdict defaults to PASSED."""
        text = "Some random text without a verdict"

        result = parse_review_output(text)

        assert result.verdict == Verdict.PASSED
        assert result.findings == []

    def test_parse_multiline_issue_and_suggestion(self) -> None:
        """Test parsing findings with multiline issue and suggestion text."""
        text = """
### Verdict: NEEDS_WORK

### Findings

1. **FINDING-001**: Complexity - Function too complex
   - File: src/ralph/services/review_loop.py:150
   - Issue: The function has a cyclomatic complexity of 15 which exceeds
     the recommended maximum of 10. Consider breaking it into smaller
     helper functions.
   - Suggestion: Extract the validation logic into a separate function
     and the processing logic into another function to reduce complexity.

---
"""
        result = parse_review_output(text)

        assert result.verdict == Verdict.NEEDS_WORK
        assert len(result.findings) == 1
        assert "cyclomatic complexity" in result.findings[0].issue
        assert "Extract the validation logic" in result.findings[0].suggestion

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string returns PASSED with no findings."""
        result = parse_review_output("")

        assert result.verdict == Verdict.PASSED
        assert result.findings == []
