"""Tests for scaffold service."""

from pathlib import Path

import pytest

from ralph.services.scaffold import ProjectType, ScaffoldService


class TestProjectType:
    """Tests for ProjectType enum."""

    def test_project_type_values(self) -> None:
        """Test that all expected project types exist."""
        assert ProjectType.PYTHON.value == "python"
        assert ProjectType.NODEJS.value == "nodejs"
        assert ProjectType.GO.value == "go"
        assert ProjectType.RUST.value == "rust"
        assert ProjectType.UNKNOWN.value == "unknown"


class TestDetectProjectType:
    """Tests for ScaffoldService.detect_project_type()."""

    def test_detects_python_with_pyproject_toml(self, tmp_path: Path) -> None:
        """Test detecting Python project via pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.PYTHON

    def test_detects_python_with_setup_py(self, tmp_path: Path) -> None:
        """Test detecting Python project via setup.py."""
        (tmp_path / "setup.py").write_text("from setuptools import setup")
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.PYTHON

    def test_detects_python_with_requirements_txt(self, tmp_path: Path) -> None:
        """Test detecting Python project via requirements.txt."""
        (tmp_path / "requirements.txt").write_text("requests>=2.0")
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.PYTHON

    def test_detects_nodejs_with_package_json(self, tmp_path: Path) -> None:
        """Test detecting Node.js project via package.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.NODEJS

    def test_detects_go_with_go_mod(self, tmp_path: Path) -> None:
        """Test detecting Go project via go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test")
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.GO

    def test_detects_rust_with_cargo_toml(self, tmp_path: Path) -> None:
        """Test detecting Rust project via Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.RUST

    def test_returns_unknown_for_empty_directory(self, tmp_path: Path) -> None:
        """Test returning UNKNOWN when no marker files exist."""
        service = ScaffoldService(project_root=tmp_path)
        assert service.detect_project_type() == ProjectType.UNKNOWN

    def test_prioritizes_python_over_nodejs(self, tmp_path: Path) -> None:
        """Test that Python is detected first when multiple markers exist."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "package.json").write_text('{"name": "test"}')
        service = ScaffoldService(project_root=tmp_path)
        # Python markers are checked first in the implementation
        assert service.detect_project_type() == ProjectType.PYTHON


class TestCreatePlansDirectory:
    """Tests for ScaffoldService.create_plans_directory()."""

    def test_creates_plans_directory(self, tmp_path: Path) -> None:
        """Test that plans/ directory is created."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_plans_directory()

        assert result == tmp_path / "plans"
        assert result.exists()
        assert result.is_dir()

    def test_returns_path_if_already_exists(self, tmp_path: Path) -> None:
        """Test that existing plans/ directory is not an error."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()

        service = ScaffoldService(project_root=tmp_path)
        result = service.create_plans_directory()

        assert result == plans_dir
        assert result.exists()


class TestCreateSpecPlaceholder:
    """Tests for ScaffoldService.create_spec_placeholder()."""

    def test_creates_spec_md_file(self, tmp_path: Path) -> None:
        """Test that SPEC.md file is created."""
        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_spec_placeholder()

        assert result == tmp_path / "plans" / "SPEC.md"
        assert result.exists()

    def test_spec_md_has_correct_structure(self, tmp_path: Path) -> None:
        """Test that SPEC.md has expected sections."""
        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_spec_placeholder()

        content = result.read_text()
        assert "# Feature Specification" in content
        assert "## Overview" in content
        assert "## Goals" in content
        assert "## Non-Goals" in content
        assert "## Requirements" in content
        assert "### Functional Requirements" in content
        assert "### Non-Functional Requirements" in content
        assert "## Technical Design" in content
        assert "## Implementation Notes" in content


class TestCreateTasksPlaceholder:
    """Tests for ScaffoldService.create_tasks_placeholder()."""

    def test_creates_tasks_json_file(self, tmp_path: Path) -> None:
        """Test that TASKS.json file is created."""
        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_tasks_placeholder()

        assert result == tmp_path / "plans" / "TASKS.json"
        assert result.exists()

    def test_tasks_json_has_valid_json(self, tmp_path: Path) -> None:
        """Test that TASKS.json contains valid JSON."""
        import json

        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_tasks_placeholder()

        content = result.read_text()
        data = json.loads(content)

        assert "project" in data
        assert "branchName" in data
        assert "description" in data
        assert "userStories" in data
        assert isinstance(data["userStories"], list)

    def test_tasks_json_has_example_story(self, tmp_path: Path) -> None:
        """Test that TASKS.json contains an example user story."""
        import json

        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_tasks_placeholder()

        data = json.loads(result.read_text())
        story = data["userStories"][0]

        assert story["id"] == "US-001"
        assert "title" in story
        assert "description" in story
        assert "acceptanceCriteria" in story
        assert story["priority"] == 1
        assert story["passes"] is False
        assert "notes" in story


class TestCreateProgressPlaceholder:
    """Tests for ScaffoldService.create_progress_placeholder()."""

    def test_creates_progress_txt_file(self, tmp_path: Path) -> None:
        """Test that PROGRESS.txt file is created."""
        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_progress_placeholder()

        assert result == tmp_path / "plans" / "PROGRESS.txt"
        assert result.exists()

    def test_progress_txt_has_correct_structure(self, tmp_path: Path) -> None:
        """Test that PROGRESS.txt has expected sections."""
        service = ScaffoldService(project_root=tmp_path)
        service.create_plans_directory()
        result = service.create_progress_placeholder()

        content = result.read_text()
        assert "# Ralph Progress Log" in content
        assert "## Codebase Patterns" in content
        assert "## Log" in content


class TestCreateClaudeMd:
    """Tests for ScaffoldService.create_claude_md()."""

    def test_creates_claude_md_file(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md file is created."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        assert result == tmp_path / "CLAUDE.md"
        assert result.exists()

    def test_claude_md_uses_directory_name_as_default(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md uses directory name when no name provided."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert tmp_path.name in content

    def test_claude_md_uses_custom_project_name(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md uses provided project name."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md(project_name="MyCustomProject")

        content = result.read_text()
        assert "MyCustomProject" in content

    def test_claude_md_has_ralph_workflow_section(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md has Ralph workflow documentation."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert "## Ralph Workflow" in content
        assert "plans/SPEC.md" in content
        assert "plans/TASKS.json" in content
        assert "plans/PROGRESS.txt" in content

    def test_claude_md_has_quality_checks_block(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md includes quality checks YAML block."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert "<!-- RALPH:CHECKS:START -->" in content
        assert "<!-- RALPH:CHECKS:END -->" in content

    def test_claude_md_has_python_checks_for_python_project(self, tmp_path: Path) -> None:
        """Test that Python projects get Python-specific quality checks."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert "uv run pyright" in content
        assert "uv run ruff check" in content
        assert "uv run pytest" in content

    def test_claude_md_has_nodejs_checks_for_nodejs_project(self, tmp_path: Path) -> None:
        """Test that Node.js projects get Node.js-specific quality checks."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert "npm run typecheck" in content
        assert "npm run lint" in content
        assert "npm test" in content

    def test_claude_md_has_go_checks_for_go_project(self, tmp_path: Path) -> None:
        """Test that Go projects get Go-specific quality checks."""
        (tmp_path / "go.mod").write_text("module test")
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert "go build" in content
        assert "go vet" in content
        assert "go test" in content

    def test_claude_md_has_rust_checks_for_rust_project(self, tmp_path: Path) -> None:
        """Test that Rust projects get Rust-specific quality checks."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_claude_md()

        content = result.read_text()
        assert "cargo build" in content
        assert "cargo clippy" in content
        assert "cargo test" in content


class TestCreateAgentsMd:
    """Tests for ScaffoldService.create_agents_md()."""

    def test_creates_agents_md_file(self, tmp_path: Path) -> None:
        """Test that AGENTS.md file is created."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_agents_md()

        assert result == tmp_path / "AGENTS.md"
        assert result.exists()

    def test_agents_md_uses_directory_name_as_default(self, tmp_path: Path) -> None:
        """Test that AGENTS.md uses directory name when no name provided."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_agents_md()

        content = result.read_text()
        assert tmp_path.name in content

    def test_agents_md_uses_custom_project_name(self, tmp_path: Path) -> None:
        """Test that AGENTS.md uses provided project name."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_agents_md(project_name="MyCustomProject")

        content = result.read_text()
        assert "MyCustomProject" in content

    def test_agents_md_has_ralph_workflow_section(self, tmp_path: Path) -> None:
        """Test that AGENTS.md has Ralph workflow documentation."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_agents_md()

        content = result.read_text()
        assert "## Ralph Workflow" in content
        assert "plans/SPEC.md" in content
        assert "plans/TASKS.json" in content
        assert "plans/PROGRESS.txt" in content

    def test_agents_md_references_claude_md(self, tmp_path: Path) -> None:
        """Test that AGENTS.md references CLAUDE.md for quality checks."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.create_agents_md()

        content = result.read_text()
        assert "CLAUDE.md" in content


class TestScaffoldAll:
    """Tests for ScaffoldService.scaffold_all()."""

    def test_creates_all_files(self, tmp_path: Path) -> None:
        """Test that scaffold_all creates all expected files."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.scaffold_all()

        assert "plans_dir" in result
        assert "spec" in result
        assert "tasks" in result
        assert "progress" in result
        assert "claude_md" in result
        assert "agents_md" in result

        assert (tmp_path / "plans").exists()
        assert (tmp_path / "plans" / "SPEC.md").exists()
        assert (tmp_path / "plans" / "TASKS.json").exists()
        assert (tmp_path / "plans" / "PROGRESS.txt").exists()
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()

    def test_scaffold_all_uses_project_name(self, tmp_path: Path) -> None:
        """Test that scaffold_all passes project name to subcommands."""
        service = ScaffoldService(project_root=tmp_path)
        service.scaffold_all(project_name="TestProject")

        claude_content = (tmp_path / "CLAUDE.md").read_text()
        agents_content = (tmp_path / "AGENTS.md").read_text()

        assert "TestProject" in claude_content
        assert "TestProject" in agents_content

    def test_scaffold_all_returns_correct_paths(self, tmp_path: Path) -> None:
        """Test that scaffold_all returns paths to created files."""
        service = ScaffoldService(project_root=tmp_path)
        result = service.scaffold_all()

        assert result["plans_dir"] == tmp_path / "plans"
        assert result["spec"] == tmp_path / "plans" / "SPEC.md"
        assert result["tasks"] == tmp_path / "plans" / "TASKS.json"
        assert result["progress"] == tmp_path / "plans" / "PROGRESS.txt"
        assert result["claude_md"] == tmp_path / "CLAUDE.md"
        assert result["agents_md"] == tmp_path / "AGENTS.md"


class TestGetQualityChecksYaml:
    """Tests for ScaffoldService._get_quality_checks_yaml()."""

    def test_python_checks_include_all_tools(self, tmp_path: Path) -> None:
        """Test Python quality checks include pyright, ruff, pytest."""
        service = ScaffoldService(project_root=tmp_path)
        yaml = service._get_quality_checks_yaml(ProjectType.PYTHON)

        assert "pyright" in yaml
        assert "ruff check" in yaml
        assert "ruff format" in yaml
        assert "pytest" in yaml

    def test_nodejs_checks_include_all_tools(self, tmp_path: Path) -> None:
        """Test Node.js quality checks include typecheck, lint, test."""
        service = ScaffoldService(project_root=tmp_path)
        yaml = service._get_quality_checks_yaml(ProjectType.NODEJS)

        assert "npm run typecheck" in yaml
        assert "npm run lint" in yaml
        assert "npm run format:check" in yaml
        assert "npm test" in yaml

    def test_go_checks_include_all_tools(self, tmp_path: Path) -> None:
        """Test Go quality checks include build, vet, lint, test."""
        service = ScaffoldService(project_root=tmp_path)
        yaml = service._get_quality_checks_yaml(ProjectType.GO)

        assert "go build" in yaml
        assert "go vet" in yaml
        assert "golangci-lint run" in yaml
        assert "go test" in yaml

    def test_rust_checks_include_all_tools(self, tmp_path: Path) -> None:
        """Test Rust quality checks include build, clippy, fmt, test."""
        service = ScaffoldService(project_root=tmp_path)
        yaml = service._get_quality_checks_yaml(ProjectType.RUST)

        assert "cargo build" in yaml
        assert "cargo clippy" in yaml
        assert "cargo fmt" in yaml
        assert "cargo test" in yaml

    def test_unknown_checks_have_generic_template(self, tmp_path: Path) -> None:
        """Test unknown project type gets generic quality checks."""
        service = ScaffoldService(project_root=tmp_path)
        yaml = service._get_quality_checks_yaml(ProjectType.UNKNOWN)

        assert "Configure your lint command" in yaml
        assert "Configure your test command" in yaml


class TestScaffoldServiceModel:
    """Tests for ScaffoldService Pydantic model configuration."""

    def test_accepts_path_type(self, tmp_path: Path) -> None:
        """Test that ScaffoldService accepts Path for project_root."""
        service = ScaffoldService(project_root=tmp_path)
        assert service.project_root == tmp_path

    def test_project_root_is_required(self) -> None:
        """Test that project_root is a required field."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ScaffoldService()  # type: ignore[call-arg]
