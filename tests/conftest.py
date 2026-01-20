"""Shared pytest fixtures for Ralph CLI tests."""

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def normalize_paths(text: str) -> str:
    r"""Normalize path separators for cross-platform comparison.

    Converts Windows-style backslashes to forward slashes so that
    path-related test assertions work consistently on both Windows
    and Unix platforms.

    Args:
        text: Text containing paths with potentially mixed separators.

    Returns:
        Text with all backslashes converted to forward slashes.

    Example:
        >>> normalize_paths("plans\\TASKS.json")
        'plans/TASKS.json'
        >>> normalize_paths("C:\\Users\\test\\file.py")
        'C:/Users/test/file.py'
    """
    return text.replace("\\", "/")


@pytest.fixture
def path_normalizer():
    """Provide normalize_paths function as a fixture.

    Returns:
        The normalize_paths function for path separator normalization.

    Example:
        def test_path_output(path_normalizer):
            actual = some_function_returning_path()
            assert path_normalizer(actual) == "expected/path/here"
    """
    return normalize_paths


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for testing commands."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory.

    Args:
        tmp_path: pytest's built-in tmp_path fixture.

    Returns:
        Path to the temporary project directory.
    """
    return tmp_path


@pytest.fixture
def python_project(temp_project: Path) -> Path:
    """Create a temporary Python project with pyproject.toml.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the Python project directory.
    """
    (temp_project / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")
    return temp_project


@pytest.fixture
def nodejs_project(temp_project: Path) -> Path:
    """Create a temporary Node.js project with package.json.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the Node.js project directory.
    """
    (temp_project / "package.json").write_text('{"name": "test-project"}\n')
    return temp_project


@pytest.fixture
def skills_dir(temp_project: Path) -> Path:
    """Create a skills directory with a valid skill.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the skills directory.
    """
    skills_path = temp_project / "skills"
    skills_path.mkdir()

    skill_path = skills_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text(
        '---\nname: "test-skill"\ndescription: "A test skill"\n---\n\n# Test Skill\n'
    )

    return skills_path


@pytest.fixture
def sample_tasks_json() -> dict:
    """Return sample TASKS.json content."""
    return {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "First story",
                "description": "As a user, I want feature A",
                "acceptanceCriteria": ["Criterion A1", "Typecheck passes"],
                "priority": 1,
                "passes": True,
                "notes": "Completed",
            },
            {
                "id": "US-002",
                "title": "Second story",
                "description": "As a user, I want feature B",
                "acceptanceCriteria": ["Criterion B1", "Criterion B2"],
                "priority": 2,
                "passes": False,
                "notes": "",
            },
            {
                "id": "US-003",
                "title": "Third story",
                "description": "As a user, I want feature C",
                "acceptanceCriteria": ["Criterion C1"],
                "priority": 3,
                "passes": False,
                "notes": "",
            },
        ],
    }


@pytest.fixture
def all_complete_tasks_json() -> dict:
    """Return TASKS.json content with all stories complete."""
    return {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "First story",
                "description": "As a user, I want feature A",
                "acceptanceCriteria": ["Criterion A1"],
                "priority": 1,
                "passes": True,
                "notes": "",
            },
        ],
    }


@pytest.fixture
def valid_tasks_json_str() -> str:
    """Return a valid TASKS.json content string."""
    tasks = {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "Test story",
                "description": "As a user, I want to test",
                "acceptanceCriteria": ["Criterion 1", "Typecheck passes"],
                "priority": 1,
                "passes": False,
                "notes": "",
            }
        ],
    }
    return json.dumps(tasks)


@pytest.fixture
def initialized_project(temp_project: Path, sample_tasks_json: dict) -> Path:
    """Create a temporary project with plans/TASKS.json.

    Args:
        temp_project: Temporary project directory.
        sample_tasks_json: Sample tasks JSON content.

    Returns:
        Path to the initialized project directory.
    """
    plans_dir = temp_project / "plans"
    plans_dir.mkdir()

    tasks_file = plans_dir / "TASKS.json"
    tasks_file.write_text(json.dumps(sample_tasks_json, indent=2))

    progress_file = plans_dir / "PROGRESS.txt"
    progress_file.write_text("# Progress Log\n\n")

    return temp_project


@pytest.fixture
def initialized_project_with_spec(temp_project: Path) -> Path:
    """Create a temporary project with plans/ directory and SPEC.md.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the initialized project directory.
    """
    plans_dir = temp_project / "plans"
    plans_dir.mkdir()

    spec_file = plans_dir / "SPEC.md"
    spec_file.write_text("# Feature Spec\n\nThis is a test specification.")

    return temp_project
