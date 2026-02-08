"""Tests for ReviewerConfigWriter CLAUDE.md manipulation."""

from pathlib import Path

from ralph.models.reviewer import ReviewerConfig, ReviewerLevel
from ralph.services import ReviewerConfigWriter, has_reviewer_config, write_reviewer_config


def _make_reviewers() -> list[ReviewerConfig]:
    """Build a small reviewer list for testing."""
    return [
        ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        ),
        ReviewerConfig(
            name="repo-structure",
            skill="reviewers/repo-structure",
            level=ReviewerLevel.warning,
        ),
    ]


class TestHasReviewerConfig:
    """Tests for has_reviewer_config detection."""

    def test_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        """Test that missing file returns False."""
        writer = ReviewerConfigWriter(path=tmp_path / "CLAUDE.md")
        assert writer.has_reviewer_config() is False

    def test_returns_false_when_no_markers(self, tmp_path: Path) -> None:
        """Test that file without markers returns False."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n\nSome content.\n")

        writer = ReviewerConfigWriter(path=claude_md)
        assert writer.has_reviewer_config() is False

    def test_returns_true_when_markers_present(self, tmp_path: Path) -> None:
        """Test that file with markers returns True."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n"
            "<!-- RALPH:REVIEWERS:START -->\n"
            "```yaml\n"
            "reviewers:\n"
            "  - name: test\n"
            "    skill: reviewers/test\n"
            "    level: blocking\n"
            "```\n"
            "<!-- RALPH:REVIEWERS:END -->\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        assert writer.has_reviewer_config() is True


class TestWriteReviewerConfigNoMarkers:
    """Tests for writing config when markers don't exist."""

    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        """Test that writing to a non-existent file creates it."""
        claude_md = tmp_path / "CLAUDE.md"
        reviewers = _make_reviewers()

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(reviewers)

        assert claude_md.exists()
        content = claude_md.read_text()
        assert "<!-- RALPH:REVIEWERS:START -->" in content
        assert "<!-- RALPH:REVIEWERS:END -->" in content
        assert "python-code" in content

    def test_appends_section_when_no_markers_and_no_project_specific(self, tmp_path: Path) -> None:
        """Test config appended at end when no markers and no Project-Specific heading."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nSome overview.\n")

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert content.startswith("# My Project\n\nSome overview.\n")
        assert "## Reviewers" in content
        assert "<!-- RALPH:REVIEWERS:START -->" in content
        assert "<!-- RALPH:REVIEWERS:END -->" in content

    def test_inserts_before_project_specific_heading(self, tmp_path: Path) -> None:
        """Test config inserted before '## Project-Specific Instructions' when present."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# My Project\n\n"
            "## Overview\n\nSome overview.\n\n"
            "## Project-Specific Instructions\n\n"
            "### Commands\n\nSome commands.\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        reviewers_pos = content.index("## Reviewers")
        project_specific_pos = content.index("## Project-Specific Instructions")
        assert reviewers_pos < project_specific_pos

    def test_preserves_content_before_insertion_point(self, tmp_path: Path) -> None:
        """Test content before the insertion point is preserved."""
        claude_md = tmp_path / "CLAUDE.md"
        original_header = "# My Project\n\n## Overview\n\nSome overview.\n\n"
        claude_md.write_text(
            original_header + "## Project-Specific Instructions\n\nSpecific stuff.\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert content.startswith(original_header)

    def test_preserves_content_after_insertion_point(self, tmp_path: Path) -> None:
        """Test content after the insertion point is preserved."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# My Project\n\n"
            "## Project-Specific Instructions\n\n"
            "### Commands\n\nKeep this content.\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert "### Commands\n\nKeep this content.\n" in content


class TestWriteReviewerConfigWithMarkers:
    """Tests for writing config when markers already exist."""

    def test_replaces_content_between_markers(self, tmp_path: Path) -> None:
        """Test that existing config between markers is replaced."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n"
            "<!-- RALPH:REVIEWERS:START -->\n"
            "```yaml\n"
            "reviewers:\n"
            "  - name: old-reviewer\n"
            "    skill: reviewers/old\n"
            "    level: warning\n"
            "```\n"
            "<!-- RALPH:REVIEWERS:END -->\n\n"
            "## Other Section\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert "old-reviewer" not in content
        assert "python-code" in content
        assert "repo-structure" in content

    def test_preserves_content_before_markers(self, tmp_path: Path) -> None:
        """Test content before markers is untouched after replacement."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n"
            "Before content stays.\n\n"
            "<!-- RALPH:REVIEWERS:START -->\n"
            "```yaml\n"
            "reviewers:\n"
            "  - name: old\n"
            "    skill: reviewers/old\n"
            "    level: blocking\n"
            "```\n"
            "<!-- RALPH:REVIEWERS:END -->\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert content.startswith("# Project\n\nBefore content stays.\n\n")

    def test_preserves_content_after_markers(self, tmp_path: Path) -> None:
        """Test content after markers is untouched after replacement."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "<!-- RALPH:REVIEWERS:START -->\n"
            "```yaml\n"
            "reviewers:\n"
            "  - name: old\n"
            "    skill: reviewers/old\n"
            "    level: blocking\n"
            "```\n"
            "<!-- RALPH:REVIEWERS:END -->\n\n"
            "## Keep This Section\n\nImportant content.\n"
        )

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert "## Keep This Section\n\nImportant content.\n" in content

    def test_languages_field_preserved_in_output(self, tmp_path: Path) -> None:
        """Test that the languages field is written correctly in YAML."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n")

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(_make_reviewers())

        content = claude_md.read_text()
        assert "languages: [python]" in content

    def test_reviewer_without_languages_omits_field(self, tmp_path: Path) -> None:
        """Test that reviewers without languages don't include the field."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n")

        reviewers = [
            ReviewerConfig(
                name="code-simplifier",
                skill="reviewers/code-simplifier",
                level=ReviewerLevel.blocking,
            ),
        ]

        writer = ReviewerConfigWriter(path=claude_md)
        writer.write_reviewer_config(reviewers)

        content = claude_md.read_text()
        lines_with_languages = [line for line in content.splitlines() if "languages:" in line]
        assert len(lines_with_languages) == 0


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_has_reviewer_config_function(self, tmp_path: Path) -> None:
        """Test has_reviewer_config convenience function."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# No markers\n")

        assert has_reviewer_config(claude_md) is False

    def test_write_reviewer_config_function(self, tmp_path: Path) -> None:
        """Test write_reviewer_config convenience function."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n")

        write_reviewer_config(claude_md, _make_reviewers())

        content = claude_md.read_text()
        assert "<!-- RALPH:REVIEWERS:START -->" in content
        assert "python-code" in content
