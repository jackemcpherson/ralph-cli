"""Pydantic models for quality check configuration."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class QualityCheck(BaseModel):
    """A single quality check definition."""

    name: str = Field(..., description="Name of the check (e.g., 'typecheck')")
    command: str = Field(..., description="Command to run for this check")
    required: bool = Field(default=True, description="Whether this check must pass for success")


class QualityChecks(BaseModel):
    """Container for quality check definitions."""

    checks: list[QualityCheck] = Field(default_factory=list, description="List of quality checks")


# Regex pattern to extract YAML between RALPH:CHECKS markers
_CHECKS_PATTERN = re.compile(
    r"<!--\s*RALPH:CHECKS:START\s*-->\s*"
    r"```yaml\s*\n"
    r"(.*?)"
    r"```\s*\n"
    r"<!--\s*RALPH:CHECKS:END\s*-->",
    re.DOTALL,
)


def parse_quality_checks(content: str) -> QualityChecks:
    """Parse quality checks from CLAUDE.md content.

    Extracts the YAML block between RALPH:CHECKS:START and RALPH:CHECKS:END
    markers and validates it against the QualityChecks model.

    Args:
        content: The content of a CLAUDE.md file

    Returns:
        QualityChecks model with parsed checks, or empty QualityChecks
        if the markers are missing or content is malformed.
    """
    match = _CHECKS_PATTERN.search(content)
    if not match:
        return QualityChecks()

    yaml_content = match.group(1)
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return QualityChecks()
        return QualityChecks.model_validate(data)
    except (yaml.YAMLError, ValueError):
        return QualityChecks()


def load_quality_checks(path: Path) -> QualityChecks:
    """Load quality checks from a CLAUDE.md file.

    Args:
        path: Path to the CLAUDE.md file

    Returns:
        QualityChecks model with parsed checks, or empty QualityChecks
        if the file doesn't exist or content is malformed.
    """
    if not path.exists():
        return QualityChecks()

    content = path.read_text(encoding="utf-8")
    return parse_quality_checks(content)
