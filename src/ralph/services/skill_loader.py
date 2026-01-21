"""Skill path loader service for Ralph CLI.

This module provides a service for locating skill files on disk,
enabling commands to reference skills via @file syntax in Claude Code.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SkillNotFoundError(Exception):
    """Raised when a requested skill file cannot be found.

    Attributes:
        skill_name: The name of the skill that was not found.
        skill_path: The path where the skill was expected.
    """

    def __init__(self, skill_name: str, skill_path: Path) -> None:
        """Initialize SkillNotFoundError.

        Args:
            skill_name: The name of the skill that was not found.
            skill_path: The path where the skill was expected.
        """
        self.skill_name = skill_name
        self.skill_path = skill_path
        super().__init__(f"Skill '{skill_name}' not found. Expected at: {skill_path}")


class SkillLoader(BaseModel):
    """Service for locating skill files on disk.

    Locates skill definitions in the skills directory, allowing
    commands to reference skills via @file syntax in Claude Code.

    Attributes:
        skills_dir: Path to the skills directory containing skill subdirectories.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skills_dir: Path

    def load(self, skill_name: str) -> Path:
        """Return the path to a skill file, validating it exists.

        Locates the SKILL.md file from the specified skill's directory
        and returns its path for use with @file references.

        Supports both flat paths (e.g., 'my-skill') and nested paths
        (e.g., 'ralph/prd', 'reviewers/code-simplifier', 'reviewers/language/python').

        Args:
            skill_name: The skill path relative to the skills directory.
                Can be flat (e.g., 'my-skill') or nested (e.g., 'ralph/prd').

        Returns:
            The path to the skill's SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill directory or SKILL.md file does not exist.
        """
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise SkillNotFoundError(skill_name, skill_path)

        return skill_path

    def get_content(self, skill_name: str) -> str:
        """Load and return the content of a skill file.

        Convenience method that loads the skill path and reads its content.
        Supports both flat paths and nested paths.

        Args:
            skill_name: The skill path relative to the skills directory.
                Can be flat (e.g., 'my-skill') or nested (e.g., 'ralph/prd').

        Returns:
            The content of the skill's SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill directory or SKILL.md file does not exist.
        """
        skill_path = self.load(skill_name)
        return skill_path.read_text(encoding="utf-8")
