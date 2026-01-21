"""Pydantic models for skill manifest tracking.

This module defines the data model for .ralph-manifest.json file used
to track which skills have been installed by ralph sync.

Manifest versions:
- Version 1 (legacy): installed contains flat directory names like "ralph-prd"
- Version 2 (current): installed contains nested paths like "ralph/prd"
"""

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

# Current manifest version for nested skill structure
MANIFEST_VERSION = 2


class Manifest(BaseModel):
    """Manifest model for tracking installed skills.

    Tracks which skills have been installed by ralph sync so that
    they can be cleanly removed later with ralph sync --remove.

    Attributes:
        version: Manifest format version (2 for nested paths).
        installed: List of installed skill paths (e.g., "ralph/prd").
        synced_at: ISO timestamp string of when the sync occurred.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Default version for backwards compatibility with v1 manifests
    LEGACY_VERSION: ClassVar[int] = 1

    version: int = Field(
        default=1,
        description="Manifest format version (1=flat names, 2=nested paths)",
    )
    installed: list[str] = Field(
        default_factory=list,
        description="List of installed skill paths",
    )
    synced_at: str = Field(
        ...,
        alias="syncedAt",
        description="ISO timestamp string of when the sync occurred",
    )


def load_manifest(path: Path) -> Manifest | None:
    """Load a manifest file from disk.

    Args:
        path: Path to the .ralph-manifest.json file

    Returns:
        Manifest model if file exists and is valid, None otherwise.
    """
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    return Manifest.model_validate_json(content)


def save_manifest(manifest: Manifest, path: Path) -> None:
    """Save a Manifest model to a JSON file.

    Args:
        manifest: Manifest model to save
        path: Path to write the file to
    """
    content = manifest.model_dump_json(indent=2, by_alias=True)
    path.write_text(content + "\n", encoding="utf-8")
