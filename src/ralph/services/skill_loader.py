"""Skill path loader service for Ralph CLI.

This module provides a service for locating skill files, either from
the filesystem or from bundled package resources.
"""

from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SkillNotFoundError(Exception):
    """Raised when a requested skill file cannot be found.

    Attributes:
        skill_name: The name of the skill that was not found.
        skill_path: The path where the skill was expected.
    """

    def __init__(self, skill_name: str, skill_path: Path | str) -> None:
        """Initialize SkillNotFoundError.

        Args:
            skill_name: The name of the skill that was not found.
            skill_path: The path where the skill was expected.
        """
        self.skill_name = skill_name
        self.skill_path = skill_path
        super().__init__(f"Skill '{skill_name}' not found. Expected at: {skill_path}")


class SkillLoader(BaseModel):
    """Service for locating skill files.

    Locates skill definitions either from a filesystem directory or from
    the bundled package resources. When skills_dir is None, skills are
    loaded from the bundled package.

    Attributes:
        skills_dir: Optional path to the skills directory. If None, uses
            bundled package resources.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skills_dir: Path | None = None

    def load(self, skill_name: str) -> Path:
        """Return the path to a skill file, validating it exists.

        Locates the SKILL.md file from the specified skill's directory
        and returns its path. This method requires skills_dir to be set
        since package resources don't have stable filesystem paths.

        Supports both flat paths (e.g., 'my-skill') and nested paths
        (e.g., 'ralph/prd', 'reviewers/code-simplifier', 'reviewers/language/python').

        Args:
            skill_name: The skill path relative to the skills directory.
                Can be flat (e.g., 'my-skill') or nested (e.g., 'ralph/prd').

        Returns:
            The path to the skill's SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill directory or SKILL.md file does not exist.
            ValueError: If skills_dir is None (use get_content for package resources).
        """
        if self.skills_dir is None:
            raise ValueError(
                "load() requires skills_dir to be set. "
                "Use get_content() to load from package resources."
            )

        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise SkillNotFoundError(skill_name, skill_path)

        return skill_path

    def get_content(self, skill_name: str) -> str:
        """Load and return the content of a skill file.

        Loads skill content from either the filesystem (if skills_dir is set)
        or from bundled package resources (if skills_dir is None).
        Supports both flat paths and nested paths.

        Args:
            skill_name: The skill path relative to the skills directory.
                Can be flat (e.g., 'my-skill') or nested (e.g., 'ralph/prd').

        Returns:
            The content of the skill's SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill cannot be found.
        """
        if self.skills_dir is not None:
            skill_path = self.load(skill_name)
            return skill_path.read_text(encoding="utf-8")

        return self._get_package_skill_content(skill_name)

    def _get_package_skill_content(self, skill_name: str) -> str:
        """Load skill content from bundled package resources.

        Args:
            skill_name: The skill path (e.g., 'ralph/prd' or 'reviewers/test-quality').

        Returns:
            The content of the skill's SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill cannot be found in the package.
        """
        skill_parts = skill_name.split("/")

        package_path = "ralph.skills"
        for part in skill_parts:
            package_path += f".{part.replace('-', '_')}"

        try:
            resource_files = files(package_path)
            skill_file = resource_files.joinpath("SKILL.md")

            if skill_file.is_file():
                return skill_file.read_text(encoding="utf-8")

            raise SkillNotFoundError(skill_name, f"package:{package_path}/SKILL.md")
        except (ModuleNotFoundError, TypeError) as e:
            raise SkillNotFoundError(skill_name, f"package:{package_path}/SKILL.md") from e
