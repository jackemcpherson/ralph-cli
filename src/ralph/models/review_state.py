"""Pydantic model for persisting review pipeline progress.

This module defines the ReviewState model used to track which reviewers
have completed during a review run, enabling interrupted runs to be resumed.
"""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ralph.models.reviewer import ReviewerConfig

# Default filename for the review state file
REVIEW_STATE_FILENAME = ".ralph-review-state.json"


class ReviewState(BaseModel):
    """Persistent state for a review pipeline run.

    Tracks which reviewers have been completed so that an interrupted
    review run can be resumed without re-running finished reviewers.

    Attributes:
        reviewer_names: List of configured reviewer names for this run.
        completed: Mapping of reviewer name to pass/fail status.
        timestamp: ISO 8601 string of when the state was last updated.
        config_hash: Hash of the reviewer configuration for change detection.
    """

    model_config = ConfigDict(populate_by_name=True)

    reviewer_names: list[str] = Field(
        ..., description="List of configured reviewer names for this run"
    )
    completed: dict[str, bool] = Field(
        default_factory=dict,
        description="Mapping of reviewer name to pass/fail status",
    )
    timestamp: str = Field(..., description="ISO 8601 string of when the state was last updated")
    config_hash: str = Field(
        ..., description="Hash of the reviewer configuration for change detection"
    )

    @staticmethod
    def compute_config_hash(reviewers: list[ReviewerConfig]) -> str:
        """Compute a deterministic hash from a list of ReviewerConfig objects.

        The hash captures reviewer names, skills, and levels so that any
        configuration change invalidates existing state.

        Args:
            reviewers: List of ReviewerConfig objects to hash.

        Returns:
            Hex digest string of the configuration hash.
        """
        data = [
            {
                "name": r.name,
                "skill": r.skill,
                "level": r.level.value,
                "languages": sorted(r.languages) if r.languages else None,
            }
            for r in reviewers
        ]
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def save(self, path: Path) -> None:
        """Save the review state to a JSON file.

        Args:
            path: Path to write the state file to.
        """
        content = self.model_dump_json(indent=2)
        path.write_text(content + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ReviewState | None":
        """Load review state from a JSON file.

        Args:
            path: Path to the state file.

        Returns:
            ReviewState if the file exists and is valid, None otherwise.
        """
        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            return cls.model_validate_json(content)
        except (ValueError, json.JSONDecodeError):
            return None
