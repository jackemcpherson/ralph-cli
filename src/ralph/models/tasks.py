"""Pydantic models for TASKS.json format."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class UserStory(BaseModel):
    """A single user story in the task list."""

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
    """Root model for TASKS.json file."""

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
