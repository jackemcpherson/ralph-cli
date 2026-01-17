"""Pydantic models for TASKS.json format.

This module defines the data models for the TASKS.json file used
in the Ralph workflow to track user stories and their completion status.
"""

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class UserStory(BaseModel):
    """A single user story in the task list.

    Represents an atomic unit of work with acceptance criteria,
    priority ordering, and pass/fail tracking for iterations.

    Attributes:
        id: Unique story identifier (e.g., US-001).
        title: Short title of the story.
        description: Full user story description.
        acceptance_criteria: List of criteria that must be met.
        priority: Priority ordering (lower = higher priority).
        passes: Whether the story has passed all checks.
        notes: Implementation notes added during iteration.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique story identifier (e.g., US-001)")
    title: str = Field(..., description="Short title of the story")
    description: str = Field(..., description="User story description")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        alias="acceptanceCriteria",
        description="List of acceptance criteria",
    )
    priority: int = Field(..., description="Priority (lower = higher priority)")
    passes: bool = Field(default=False, description="Whether the story passes checks")
    notes: str = Field(default="", description="Implementation notes")


class TasksFile(BaseModel):
    """Root model for TASKS.json file.

    Contains project metadata and a list of user stories that make up
    the feature being implemented in the Ralph workflow.

    Attributes:
        project: Project name.
        branch_name: Git branch name for this feature.
        description: Feature description.
        user_stories: List of user stories to implement.
    """

    model_config = ConfigDict(populate_by_name=True)

    project: str = Field(..., description="Project name")
    branch_name: str = Field(
        ..., alias="branchName", description="Git branch name for this feature"
    )
    description: str = Field(..., description="Feature description")
    user_stories: list[UserStory] = Field(
        default_factory=list, alias="userStories", description="List of user stories"
    )


def load_tasks(path: Path) -> TasksFile:
    """Load and validate a TASKS.json file.

    Args:
        path: Path to the TASKS.json file

    Returns:
        Validated TasksFile model

    Raises:
        FileNotFoundError: If the file doesn't exist
        pydantic.ValidationError: If the file content is invalid
    """
    content = path.read_text(encoding="utf-8")
    return TasksFile.model_validate_json(content)


def save_tasks(tasks: TasksFile, path: Path) -> None:
    """Save a TasksFile model to a JSON file.

    Args:
        tasks: TasksFile model to save
        path: Path to write the file to
    """
    content = tasks.model_dump_json(indent=2, by_alias=True)
    path.write_text(content + "\n", encoding="utf-8")
