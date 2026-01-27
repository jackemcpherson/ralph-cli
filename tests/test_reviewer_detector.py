"""Tests for reviewer detection service."""

from pathlib import Path

from ralph.models.reviewer import ReviewerLevel
from ralph.services import ReviewerDetector, detect_reviewers


class TestReviewerDetector:
    """Tests for ReviewerDetector detection logic."""

    def test_always_includes_universal_reviewers(self, tmp_path: Path) -> None:
        """Test that code-simplifier and repo-structure are always included."""
        detector = ReviewerDetector(project_root=tmp_path)
        reviewers = detector.detect_reviewers()

        names = [r.name for r in reviewers]
        assert "code-simplifier" in names
        assert "repo-structure" in names

    def test_universal_reviewer_skills_are_correct(self, tmp_path: Path) -> None:
        """Test that universal reviewers have correct skill paths."""
        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        reviewers_by_name = {r.name: r for r in reviewers}

        assert reviewers_by_name["code-simplifier"].skill == "reviewers/code-simplifier"
        assert reviewers_by_name["repo-structure"].skill == "reviewers/repo-structure"

    def test_detects_python_project(self, tmp_path: Path) -> None:
        """Test Python project detection adds python-code reviewer."""
        (tmp_path / "main.py").write_text("print('hello')\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "python-code" in names
        python_reviewer = next(r for r in reviewers if r.name == "python-code")
        assert python_reviewer.skill == "reviewers/language/python"
        assert python_reviewer.level == ReviewerLevel.blocking
        assert python_reviewer.languages == ["python"]

    def test_detects_python_in_subdirectory(self, tmp_path: Path) -> None:
        """Test Python detection works for files in subdirectories."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("def main(): pass\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "python-code" in names

    def test_detects_bicep_project(self, tmp_path: Path) -> None:
        """Test Bicep project detection adds bicep reviewer."""
        (tmp_path / "main.bicep").write_text("param location string\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "bicep" in names
        bicep_reviewer = next(r for r in reviewers if r.name == "bicep")
        assert bicep_reviewer.skill == "reviewers/language/bicep"
        assert bicep_reviewer.level == ReviewerLevel.blocking
        assert bicep_reviewer.languages == ["bicep"]

    def test_detects_bicep_in_subdirectory(self, tmp_path: Path) -> None:
        """Test Bicep detection works for files in subdirectories."""
        infra_dir = tmp_path / "infra"
        infra_dir.mkdir()
        (infra_dir / "storage.bicep").write_text("resource storage\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "bicep" in names

    def test_detects_github_actions_yml(self, tmp_path: Path) -> None:
        """Test GitHub Actions detection for .yml files."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("name: CI\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "github-actions" in names
        gh_reviewer = next(r for r in reviewers if r.name == "github-actions")
        assert gh_reviewer.skill == "reviewers/github-actions"
        assert gh_reviewer.level == ReviewerLevel.warning

    def test_detects_github_actions_yaml(self, tmp_path: Path) -> None:
        """Test GitHub Actions detection for .yaml files."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "deploy.yaml").write_text("name: Deploy\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "github-actions" in names

    def test_no_github_actions_without_workflows_dir(self, tmp_path: Path) -> None:
        """Test github-actions reviewer not added without workflows directory."""
        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "github-actions" not in names

    def test_no_github_actions_with_empty_workflows_dir(self, tmp_path: Path) -> None:
        """Test github-actions reviewer not added when workflows dir is empty."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "github-actions" not in names

    def test_detects_test_files_with_prefix(self, tmp_path: Path) -> None:
        """Test test-quality reviewer added for test_*.py files."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("def test_example(): pass\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "test-quality" in names
        test_reviewer = next(r for r in reviewers if r.name == "test-quality")
        assert test_reviewer.skill == "reviewers/test-quality"
        assert test_reviewer.level == ReviewerLevel.blocking

    def test_detects_test_files_with_suffix(self, tmp_path: Path) -> None:
        """Test test-quality reviewer added for *_test.py files."""
        (tmp_path / "main_test.py").write_text("def test_example(): pass\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "test-quality" in names

    def test_detects_changelog_adds_release_reviewer(self, tmp_path: Path) -> None:
        """Test release reviewer added when CHANGELOG.md exists."""
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "release" in names
        release_reviewer = next(r for r in reviewers if r.name == "release")
        assert release_reviewer.skill == "reviewers/release"
        assert release_reviewer.level == ReviewerLevel.blocking

    def test_no_release_without_changelog(self, tmp_path: Path) -> None:
        """Test release reviewer not added without CHANGELOG.md."""
        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        assert "release" not in names

    def test_detects_multiple_project_types(self, tmp_path: Path) -> None:
        """Test detection works for projects with multiple characteristics."""
        # Create Python project with tests, GH Actions, and changelog
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "test_main.py").write_text("def test(): pass\n")
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("name: CI\n")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")

        reviewers = ReviewerDetector(project_root=tmp_path).detect_reviewers()
        names = [r.name for r in reviewers]

        # Universal reviewers
        assert "code-simplifier" in names
        assert "repo-structure" in names
        # Detected reviewers
        assert "python-code" in names
        assert "github-actions" in names
        assert "test-quality" in names
        assert "release" in names


class TestDetectReviewersFunction:
    """Tests for the detect_reviewers convenience function."""

    def test_detect_reviewers_works(self, tmp_path: Path) -> None:
        """Test detect_reviewers convenience function."""
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")

        reviewers = detect_reviewers(tmp_path)
        names = [r.name for r in reviewers]

        assert "code-simplifier" in names
        assert "repo-structure" in names
        assert "python-code" in names
        assert "release" in names

    def test_empty_project_returns_only_universal(self, tmp_path: Path) -> None:
        """Test empty project returns only universal reviewers."""
        reviewers = detect_reviewers(tmp_path)
        names = [r.name for r in reviewers]

        assert names == ["code-simplifier", "repo-structure"]
