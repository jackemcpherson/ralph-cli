"""Prompt building utilities for Ralph CLI.

This module provides utilities for building prompts with skill content.
"""

from pathlib import Path

from ralph.services.skill_loader import SkillLoader, SkillNotFoundError


def build_skill_prompt(
    skill_name: str,
    context: str,
    skills_dir: Path | None = None,
) -> str:
    """Build a prompt with inlined skill content.

    Creates a prompt that includes the skill instructions inline,
    followed by context for the session. When skills_dir is None,
    loads skills from bundled package resources.

    Args:
        skill_name: Skill name (e.g., 'ralph/prd', 'reviewers/test-quality').
        context: Context section to append.
        skills_dir: Optional custom skills directory. If None, uses bundled skills.

    Returns:
        Prompt string with skill content inlined.

    Raises:
        SkillNotFoundError: If skill doesn't exist.
    """
    loader = SkillLoader(skills_dir=skills_dir)
    skill_content = loader.get_content(skill_name)

    return f"""Follow these instructions:

{skill_content}

{context}"""


__all__ = ["build_skill_prompt", "SkillNotFoundError"]
