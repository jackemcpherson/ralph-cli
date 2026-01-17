"""Tests for Pydantic models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ralph.models import (
    QualityCheck,
    QualityChecks,
    TasksFile,
    UserStory,
    load_quality_checks,
    load_tasks,
    parse_quality_checks,
    save_tasks,
)


class TestUserStory:
    """Tests for the UserStory model."""

    def test_user_story_valid_with_all_fields(self) -> None:
        """Test UserStory with all fields provided."""
        story = UserStory(
            id="US-001",
            title="Test story",
            description="As a user, I want to test",
            acceptance_criteria=["Criterion 1", "Typecheck passes"],
            priority=1,
            passes=False,
            notes="Some notes",
        )

        assert story.id == "US-001"
        assert story.title == "Test story"
        assert story.description == "As a user, I want to test"
        assert story.acceptance_criteria == ["Criterion 1", "Typecheck passes"]
        assert story.priority == 1
        assert story.passes is False
        assert story.notes == "Some notes"

    def test_user_story_valid_with_minimal_fields(self) -> None:
        """Test UserStory with only required fields (using defaults)."""
        story = UserStory(
            id="US-002",
            title="Minimal story",
            description="A minimal user story",
            priority=1,
        )

        assert story.id == "US-002"
        assert story.acceptance_criteria == []  # default
        assert story.passes is False  # default
        assert story.notes == ""  # default

    def test_user_story_camel_case_alias(self) -> None:
        """Test UserStory accepts camelCase alias for acceptance_criteria."""
        # Using camelCase as from JSON
        story = UserStory(
            id="US-003",
            title="Alias test",
            description="Testing camelCase alias",
            acceptanceCriteria=["AC1", "AC2"],
            priority=1,
        )

        assert story.acceptance_criteria == ["AC1", "AC2"]

    def test_user_story_serialization_uses_alias(self) -> None:
        """Test UserStory serialization uses camelCase alias."""
        story = UserStory(
            id="US-004",
            title="Serialization test",
            description="Testing serialization",
            acceptance_criteria=["AC1"],
            priority=1,
        )

        json_str = story.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert "acceptanceCriteria" in data
        assert "acceptance_criteria" not in data

    def test_user_story_missing_required_fields(self) -> None:
        """Test UserStory raises ValidationError for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            UserStory(id="US-005", title="Missing fields")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors}
        assert "description" in missing_fields
        assert "priority" in missing_fields

    def test_user_story_invalid_type_for_priority(self) -> None:
        """Test UserStory raises ValidationError for invalid priority type."""
        with pytest.raises(ValidationError):
            UserStory(
                id="US-006",
                title="Invalid priority",
                description="Testing invalid priority",
                priority="high",  # type: ignore[arg-type]
            )

    def test_user_story_invalid_type_for_passes(self) -> None:
        """Test UserStory coerces or rejects invalid passes type."""
        # Pydantic may coerce some values; test with definitely invalid value
        with pytest.raises(ValidationError):
            UserStory(
                id="US-007",
                title="Invalid passes",
                description="Testing invalid passes",
                priority=1,
                passes="maybe",  # type: ignore[arg-type]
            )


class TestTasksFile:
    """Tests for the TasksFile model."""

    def test_tasks_file_valid_with_all_fields(self) -> None:
        """Test TasksFile with all fields provided."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Test story",
            priority=1,
        )
        tasks = TasksFile(
            project="TestProject",
            branch_name="ralph/test-feature",
            description="Test feature description",
            user_stories=[story],
        )

        assert tasks.project == "TestProject"
        assert tasks.branch_name == "ralph/test-feature"
        assert tasks.description == "Test feature description"
        assert len(tasks.user_stories) == 1
        assert tasks.user_stories[0].id == "US-001"

    def test_tasks_file_valid_with_minimal_fields(self) -> None:
        """Test TasksFile with only required fields."""
        tasks = TasksFile(
            project="Minimal",
            branch_name="ralph/minimal",
            description="Minimal description",
        )

        assert tasks.project == "Minimal"
        assert tasks.user_stories == []  # default

    def test_tasks_file_camel_case_aliases(self) -> None:
        """Test TasksFile accepts camelCase aliases from JSON."""
        tasks = TasksFile(
            project="AliasTest",
            branchName="ralph/alias-test",
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

        assert tasks.branch_name == "ralph/alias-test"
        assert len(tasks.user_stories) == 1
        assert tasks.user_stories[0].acceptance_criteria == ["AC1"]

    def test_tasks_file_serialization_uses_aliases(self) -> None:
        """Test TasksFile serialization uses camelCase aliases."""
        tasks = TasksFile(
            project="SerializationTest",
            branch_name="ralph/serialization",
            description="Testing serialization",
            user_stories=[
                UserStory(
                    id="US-001",
                    title="Test",
                    description="Test",
                    priority=1,
                )
            ],
        )

        json_str = tasks.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert "branchName" in data
        assert "branch_name" not in data
        assert "userStories" in data
        assert "user_stories" not in data
        assert "acceptanceCriteria" in data["userStories"][0]

    def test_tasks_file_missing_required_fields(self) -> None:
        """Test TasksFile raises ValidationError for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            TasksFile(project="MissingFields")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors}
        assert "branch_name" in missing_fields or "branchName" in missing_fields
        assert "description" in missing_fields

    def test_tasks_file_validates_nested_user_stories(self) -> None:
        """Test TasksFile validates nested UserStory objects."""
        with pytest.raises(ValidationError):
            TasksFile(
                project="NestedValidation",
                branch_name="ralph/nested",
                description="Testing nested validation",
                user_stories=[
                    {"id": "US-001", "title": "Missing fields"},  # Missing description and priority
                ],
            )

    def test_tasks_file_with_unicode_project_name(self) -> None:
        """Test TasksFile accepts unicode characters in project name."""
        tasks = TasksFile(
            project="Проект テスト 项目 🚀",
            branch_name="ralph/unicode-test",
            description="Project with unicode characters",
        )

        assert tasks.project == "Проект テスト 项目 🚀"

    def test_tasks_file_with_empty_user_stories_array(self) -> None:
        """Test TasksFile with explicitly empty userStories array."""
        tasks = TasksFile(
            project="EmptyStoriesTest",
            branch_name="ralph/empty-stories",
            description="Testing empty stories array",
            user_stories=[],
        )

        assert tasks.user_stories == []
        assert len(tasks.user_stories) == 0

    def test_tasks_file_with_very_long_description(self) -> None:
        """Test TasksFile with a very long description."""
        long_description = "A" * 10000
        tasks = TasksFile(
            project="LongDescTest",
            branch_name="ralph/long-desc",
            description=long_description,
        )

        assert len(tasks.description) == 10000

    def test_user_story_with_many_acceptance_criteria(self) -> None:
        """Test UserStory with a large number of acceptance criteria."""
        many_criteria = [f"Criterion {i}" for i in range(100)]
        story = UserStory(
            id="US-100",
            title="Many criteria story",
            description="A story with many acceptance criteria",
            acceptance_criteria=many_criteria,
            priority=1,
        )

        assert len(story.acceptance_criteria) == 100


class TestQualityCheck:
    """Tests for the QualityCheck model."""

    def test_quality_check_valid_with_all_fields(self) -> None:
        """Test QualityCheck with all fields provided."""
        check = QualityCheck(
            name="typecheck",
            command="uv run pyright",
            required=True,
        )

        assert check.name == "typecheck"
        assert check.command == "uv run pyright"
        assert check.required is True

    def test_quality_check_required_defaults_to_true(self) -> None:
        """Test QualityCheck required field defaults to True."""
        check = QualityCheck(name="lint", command="uv run ruff check .")

        assert check.required is True

    def test_quality_check_required_can_be_false(self) -> None:
        """Test QualityCheck required can be set to False."""
        check = QualityCheck(
            name="optional-check",
            command="some-command",
            required=False,
        )

        assert check.required is False

    def test_quality_check_missing_required_fields(self) -> None:
        """Test QualityCheck raises ValidationError for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            QualityCheck(name="incomplete")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors}
        assert "command" in missing_fields


class TestQualityChecks:
    """Tests for the QualityChecks model."""

    def test_quality_checks_with_multiple_checks(self) -> None:
        """Test QualityChecks with multiple check items."""
        checks = QualityChecks(
            checks=[
                QualityCheck(name="typecheck", command="uv run pyright"),
                QualityCheck(name="lint", command="uv run ruff check ."),
                QualityCheck(name="test", command="uv run pytest"),
            ]
        )

        assert len(checks.checks) == 3
        assert checks.checks[0].name == "typecheck"
        assert checks.checks[1].name == "lint"
        assert checks.checks[2].name == "test"

    def test_quality_checks_empty_list(self) -> None:
        """Test QualityChecks with empty checks list."""
        checks = QualityChecks(checks=[])
        assert checks.checks == []

    def test_quality_checks_default_is_empty(self) -> None:
        """Test QualityChecks defaults to empty list."""
        checks = QualityChecks()
        assert checks.checks == []

    def test_quality_checks_from_dict(self) -> None:
        """Test QualityChecks can be created from dict."""
        data = {
            "checks": [
                {"name": "typecheck", "command": "npm run typecheck"},
                {"name": "lint", "command": "npm run lint", "required": False},
            ]
        }
        checks = QualityChecks.model_validate(data)

        assert len(checks.checks) == 2
        assert checks.checks[0].required is True
        assert checks.checks[1].required is False


class TestLoadTasks:
    """Tests for the load_tasks function."""

    def test_load_tasks_valid_file(self, tmp_path: Path) -> None:
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
        assert tasks.branch_name == "ralph/test"
        assert len(tasks.user_stories) == 1
        assert tasks.user_stories[0].id == "US-001"

    def test_load_tasks_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading a nonexistent file raises FileNotFoundError."""
        tasks_file = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_tasks(tasks_file)

    def test_load_tasks_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON raises an error."""
        tasks_file = tmp_path / "invalid.json"
        tasks_file.write_text("not valid json {")

        with pytest.raises(ValidationError):
            load_tasks(tasks_file)

    def test_load_tasks_invalid_structure(self, tmp_path: Path) -> None:
        """Test loading JSON with invalid structure raises ValidationError."""
        tasks_file = tmp_path / "invalid_structure.json"
        tasks_file.write_text('{"invalid": "structure"}')

        with pytest.raises(ValidationError):
            load_tasks(tasks_file)

    def test_load_tasks_empty_file(self, tmp_path: Path) -> None:
        """Test loading an empty file raises an error."""
        tasks_file = tmp_path / "empty.json"
        tasks_file.write_text("")

        with pytest.raises(ValidationError):
            load_tasks(tasks_file)


class TestSaveTasks:
    """Tests for the save_tasks function."""

    def test_save_tasks_creates_file(self, tmp_path: Path) -> None:
        """Test save_tasks creates a new file."""
        tasks = TasksFile(
            project="SaveTest",
            branch_name="ralph/save-test",
            description="Testing save",
        )

        tasks_file = tmp_path / "TASKS.json"
        save_tasks(tasks, tasks_file)

        assert tasks_file.exists()

    def test_save_tasks_writes_valid_json(self, tmp_path: Path) -> None:
        """Test save_tasks writes valid JSON."""
        tasks = TasksFile(
            project="JSONTest",
            branch_name="ralph/json-test",
            description="Testing JSON output",
            user_stories=[
                UserStory(
                    id="US-001",
                    title="Test",
                    description="Test story",
                    priority=1,
                )
            ],
        )

        tasks_file = tmp_path / "TASKS.json"
        save_tasks(tasks, tasks_file)

        content = tasks_file.read_text()
        data = json.loads(content)

        assert data["project"] == "JSONTest"
        assert "userStories" in data
        assert len(data["userStories"]) == 1

    def test_save_tasks_uses_camel_case_aliases(self, tmp_path: Path) -> None:
        """Test save_tasks uses camelCase aliases in output."""
        tasks = TasksFile(
            project="AliasTest",
            branch_name="ralph/alias-test",
            description="Testing aliases",
            user_stories=[
                UserStory(
                    id="US-001",
                    title="Test",
                    description="Test story",
                    acceptance_criteria=["AC1"],
                    priority=1,
                )
            ],
        )

        tasks_file = tmp_path / "TASKS.json"
        save_tasks(tasks, tasks_file)

        content = tasks_file.read_text()
        data = json.loads(content)

        assert "branchName" in data
        assert "branch_name" not in data
        assert "userStories" in data
        assert "user_stories" not in data
        assert "acceptanceCriteria" in data["userStories"][0]

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
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
                UserStory(
                    id="US-002",
                    title="Story 2",
                    description="Second story",
                    priority=2,
                ),
            ],
        )

        tasks_file = tmp_path / "TASKS.json"
        save_tasks(original, tasks_file)
        loaded = load_tasks(tasks_file)

        assert loaded.project == original.project
        assert loaded.branch_name == original.branch_name
        assert loaded.description == original.description
        assert len(loaded.user_stories) == len(original.user_stories)
        assert loaded.user_stories[0].id == original.user_stories[0].id
        assert loaded.user_stories[0].passes == original.user_stories[0].passes
        assert loaded.user_stories[1].notes == original.user_stories[1].notes


class TestParseQualityChecks:
    """Tests for the parse_quality_checks function."""

    def test_parse_valid_checks_block(self) -> None:
        """Test parsing a valid quality checks block."""
        content = """# Project Instructions

## Quality Checks

<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
    required: true
  - name: lint
    command: uv run ruff check .
    required: true
```
<!-- RALPH:CHECKS:END -->

More content here.
"""
        checks = parse_quality_checks(content)

        assert len(checks.checks) == 2
        assert checks.checks[0].name == "typecheck"
        assert checks.checks[0].command == "uv run pyright"
        assert checks.checks[0].required is True
        assert checks.checks[1].name == "lint"

    def test_parse_checks_missing_start_marker(self) -> None:
        """Test parsing content without START marker returns empty."""
        content = """# Project Instructions

```yaml
checks:
  - name: typecheck
    command: uv run pyright
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_missing_end_marker(self) -> None:
        """Test parsing content without END marker returns empty."""
        content = """# Project Instructions

<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
```
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_no_markers(self) -> None:
        """Test parsing content without any markers returns empty."""
        content = """# Project Instructions

Just some regular content without quality checks.
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_invalid_yaml(self) -> None:
        """Test parsing invalid YAML returns empty checks."""
        content = """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: [invalid yaml
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_not_dict(self) -> None:
        """Test parsing YAML that's not a dict returns empty checks."""
        content = """<!-- RALPH:CHECKS:START -->
```yaml
- item1
- item2
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_with_optional_check(self) -> None:
        """Test parsing checks with required=false."""
        content = """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: coverage
    command: uv run pytest --cov
    required: false
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)

        assert len(checks.checks) == 1
        assert checks.checks[0].name == "coverage"
        assert checks.checks[0].required is False

    def test_parse_checks_empty_checks_list(self) -> None:
        """Test parsing block with empty checks list."""
        content = """<!-- RALPH:CHECKS:START -->
```yaml
checks: []
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_with_extra_whitespace_in_markers(self) -> None:
        """Test parsing handles extra whitespace in markers."""
        content = """<!--   RALPH:CHECKS:START   -->
```yaml
checks:
  - name: typecheck
    command: npm run typecheck
```
<!--   RALPH:CHECKS:END   -->
"""
        checks = parse_quality_checks(content)

        assert len(checks.checks) == 1
        assert checks.checks[0].name == "typecheck"


class TestLoadQualityChecks:
    """Tests for the load_quality_checks function."""

    def test_load_quality_checks_from_file(self, tmp_path: Path) -> None:
        """Test loading quality checks from a file."""
        content = """# CLAUDE.md

<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
```
<!-- RALPH:CHECKS:END -->
"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content)

        checks = load_quality_checks(claude_md)

        assert len(checks.checks) == 1
        assert checks.checks[0].name == "typecheck"

    def test_load_quality_checks_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file returns empty checks."""
        claude_md = tmp_path / "nonexistent.md"

        checks = load_quality_checks(claude_md)

        assert checks.checks == []

    def test_load_quality_checks_file_without_checks(self, tmp_path: Path) -> None:
        """Test loading file without quality checks returns empty."""
        content = """# CLAUDE.md

This file has no quality checks defined.
"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content)

        checks = load_quality_checks(claude_md)

        assert checks.checks == []
