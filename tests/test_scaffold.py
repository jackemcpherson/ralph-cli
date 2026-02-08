"""Tests for ScaffoldService.create_gitignore() method."""

from pathlib import Path

from ralph.models.review_state import REVIEW_STATE_FILENAME
from ralph.services.scaffold import ScaffoldService


class TestCreateGitignore:
    """Tests for ScaffoldService.create_gitignore()."""

    def test_creates_gitignore_when_not_exists(self, tmp_path: Path) -> None:
        """Test that .gitignore is created with the review state entry."""
        service = ScaffoldService(project_root=tmp_path)

        result = service.create_gitignore()

        assert result == tmp_path / ".gitignore"
        content = result.read_text()
        assert REVIEW_STATE_FILENAME in content.splitlines()

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """Test that entry is appended when .gitignore exists without it."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n__pycache__/\n")

        service = ScaffoldService(project_root=tmp_path)
        service.create_gitignore()

        content = gitignore.read_text()
        lines = content.splitlines()
        assert "node_modules/" in lines
        assert "__pycache__/" in lines
        assert REVIEW_STATE_FILENAME in lines

    def test_does_not_duplicate_entry(self, tmp_path: Path) -> None:
        """Test that entry is not added if already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(f"node_modules/\n{REVIEW_STATE_FILENAME}\n")

        service = ScaffoldService(project_root=tmp_path)
        service.create_gitignore()

        content = gitignore.read_text()
        assert content.count(REVIEW_STATE_FILENAME) == 1

    def test_appends_with_newline_when_missing_trailing_newline(self, tmp_path: Path) -> None:
        """Test that a newline is added before the entry if file lacks trailing newline."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/")  # No trailing newline

        service = ScaffoldService(project_root=tmp_path)
        service.create_gitignore()

        content = gitignore.read_text()
        lines = content.splitlines()
        assert "node_modules/" in lines
        assert REVIEW_STATE_FILENAME in lines

    def test_handles_empty_gitignore(self, tmp_path: Path) -> None:
        """Test that entry is added to an empty .gitignore file."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("")

        service = ScaffoldService(project_root=tmp_path)
        service.create_gitignore()

        content = gitignore.read_text()
        assert REVIEW_STATE_FILENAME in content.splitlines()

    def test_returns_gitignore_path(self, tmp_path: Path) -> None:
        """Test that create_gitignore returns the path to .gitignore."""
        service = ScaffoldService(project_root=tmp_path)

        result = service.create_gitignore()

        assert result == tmp_path / ".gitignore"


class TestScaffoldAllGitignore:
    """Tests for .gitignore integration in scaffold_all()."""

    def test_scaffold_all_creates_gitignore(self, tmp_path: Path) -> None:
        """Test that scaffold_all() includes gitignore in results."""
        service = ScaffoldService(project_root=tmp_path)

        result = service.scaffold_all()

        assert "gitignore" in result
        assert result["gitignore"] == tmp_path / ".gitignore"
        content = (tmp_path / ".gitignore").read_text()
        assert REVIEW_STATE_FILENAME in content.splitlines()

    def test_scaffold_all_preserves_existing_gitignore(self, tmp_path: Path) -> None:
        """Test that scaffold_all() appends to existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        service = ScaffoldService(project_root=tmp_path)
        service.scaffold_all()

        content = gitignore.read_text()
        lines = content.splitlines()
        assert "*.pyc" in lines
        assert REVIEW_STATE_FILENAME in lines
