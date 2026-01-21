"""Unit tests for TasksFile and UserStory models.

Focused tests for task model handling:
- Model creation and validation
- JSON serialization with camelCase aliases
- Loading/saving tasks to/from files
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ralph.models import TasksFile, UserStory, load_tasks, save_tasks


class TestUserStory:
    """Tests for the UserStory model."""

    def test_user_story_creation_and_serialization(self) -> None:
        """Test UserStory creation with camelCase alias and serialization."""
        # Test creation with camelCase alias
        story = UserStory(
            id="US-001",
            title="Test story",
            description="As a user, I want to test",
            acceptanceCriteria=["Criterion 1", "Typecheck passes"],
            priority=1,
            passes=False,
        )

        assert story.id == "US-001"
        assert story.acceptance_criteria == ["Criterion 1", "Typecheck passes"]

        # Verify serialization uses camelCase
        json_str = story.model_dump_json(by_alias=True)
        data = json.loads(json_str)
        assert "acceptanceCriteria" in data
        assert "acceptance_criteria" not in data


class TestTasksFile:
    """Tests for the TasksFile model."""

    def test_tasks_file_creation_and_serialization(self) -> None:
        """Test TasksFile with camelCase aliases from JSON."""
        tasks = TasksFile(
            project="TestProject",
            branchName="ralph/test-feature",
            description="Testing aliases",
            userStories=[
                {
                    "id": "US-001",
                    "title": "Test",
                    "description": "Test",
                    "acceptanceCriteria": ["AC1"],
                    "priority": 1,
                }
            ],
        )

        assert tasks.project == "TestProject"
        assert tasks.branch_name == "ralph/test-feature"
        assert tasks.user_stories[0].acceptance_criteria == ["AC1"]


class TestLoadSaveTasks:
    """Tests for load_tasks and save_tasks functions."""

    def test_load_tasks_from_valid_file(self, tmp_path: Path) -> None:
        """Test loading a valid TASKS.json file."""
        tasks_data = {
            "project": "TestProject",
            "branchName": "ralph/test",
            "description": "Test description",
            "userStories": [
                {
                    "id": "US-001",
                    "title": "Test story",
                    "description": "Test",
                    "acceptanceCriteria": ["AC1"],
                    "priority": 1,
                    "passes": False,
                    "notes": "",
                }
            ],
        }

        tasks_file = tmp_path / "TASKS.json"
        tasks_file.write_text(json.dumps(tasks_data))

        tasks = load_tasks(tasks_file)

        assert tasks.project == "TestProject"
        assert len(tasks.user_stories) == 1

    def test_load_tasks_error_handling(self, tmp_path: Path) -> None:
        """Test loading raises appropriate errors for invalid files."""
        # Nonexistent file
        with pytest.raises(FileNotFoundError):
            load_tasks(tmp_path / "nonexistent.json")

        # Invalid structure
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"invalid": "structure"}')
        with pytest.raises(ValidationError):
            load_tasks(invalid_file)

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        """Test that save_tasks and load_tasks are inverse operations."""
        original = TasksFile(
            project="RoundTrip",
            branch_name="ralph/round-trip",
            description="Testing round trip",
            user_stories=[
                UserStory(
                    id="US-001",
                    title="Story 1",
                    description="First story",
                    acceptance_criteria=["AC1", "AC2"],
                    priority=1,
                    passes=True,
                    notes="Completed",
                ),
            ],
        )

        tasks_file = tmp_path / "TASKS.json"
        save_tasks(original, tasks_file)

        # Verify file uses camelCase
        data = json.loads(tasks_file.read_text())
        assert "branchName" in data
        assert "userStories" in data

        # Verify round-trip
        loaded = load_tasks(tasks_file)
        assert loaded.project == original.project
        assert loaded.user_stories[0].passes == original.user_stories[0].passes
