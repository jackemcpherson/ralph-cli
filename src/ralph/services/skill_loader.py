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

        Args:
            skill_name: The name of the skill directory to load (e.g., 'ralph-prd').

        Returns:
            The path to the skill's SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill directory or SKILL.md file does not exist.
        """
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise SkillNotFoundError(skill_name, skill_path)

        return skill_path
