"""Tests for SkillLoader service."""

from pathlib import Path

import pytest

from ralph.services.skill_loader import SkillLoader, SkillNotFoundError


class TestSkillLoader:
    """Tests for SkillLoader functionality."""

    def test_load_returns_skill_path(self, tmp_path: Path) -> None:
        """Test that load returns skill path for existing skill."""
        skill_file = _create_skill(tmp_path, "my-skill")

        loader = SkillLoader(skills_dir=tmp_path / "skills")
        result = loader.load("my-skill")

        assert result == skill_file
        assert result.exists()

    def test_load_raises_for_missing_skill(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError for missing skill."""
        (tmp_path / "skills").mkdir()

        loader = SkillLoader(skills_dir=tmp_path / "skills")

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load("nonexistent")

        assert exc_info.value.skill_name == "nonexistent"

    def test_load_nested_paths(self, tmp_path: Path) -> None:
        """Test loading skills with nested paths like ralph/prd or reviewers/language/python."""
        _create_skill(tmp_path, "ralph/prd")
        _create_skill(tmp_path, "reviewers/language/python")

        loader = SkillLoader(skills_dir=tmp_path / "skills")

        result1 = loader.load("ralph/prd")
        result2 = loader.load("reviewers/language/python")

        assert result1.exists()
        assert result1.parent.name == "prd"
        assert result2.exists()
        assert result2.parent.name == "python"

    def test_get_content_returns_file_content(self, tmp_path: Path) -> None:
        """Test that get_content returns the skill file content."""
        _create_skill(tmp_path, "my-skill", content="# Custom Content")

        loader = SkillLoader(skills_dir=tmp_path / "skills")
        result = loader.get_content("my-skill")

        assert result == "# Custom Content"


def _create_skill(tmp_path: Path, skill_path: str, content: str = "# Skill") -> Path:
    """Create a skill directory with SKILL.md."""
    skill_dir = tmp_path / "skills" / skill_path
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content)
    return skill_file
