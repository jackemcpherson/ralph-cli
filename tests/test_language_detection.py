"""Tests for language detection service."""

from pathlib import Path

from ralph.services import Language, LanguageDetector, detect_languages


class TestLanguageDetector:
    """Tests for LanguageDetector detection logic."""

    def test_detects_python_from_marker_files(self, tmp_path: Path) -> None:
        """Test Python detected from pyproject.toml, setup.py, or requirements.txt."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        detector = LanguageDetector(project_root=tmp_path)

        assert Language.python in detector.detect()
        assert detector.has_language(Language.python)
        assert not detector.has_language(Language.go)

    def test_detects_javascript_and_typescript(self, tmp_path: Path) -> None:
        """Test JavaScript from package.json and TypeScript from tsconfig.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}\n')

        detected = LanguageDetector(project_root=tmp_path).detect()

        assert Language.javascript in detected
        assert Language.typescript in detected

    def test_detects_go_from_go_mod(self, tmp_path: Path) -> None:
        """Test Go detected from go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test\n")

        assert Language.go in LanguageDetector(project_root=tmp_path).detect()

    def test_detects_rust_from_cargo_toml(self, tmp_path: Path) -> None:
        """Test Rust detected from Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        assert Language.rust in LanguageDetector(project_root=tmp_path).detect()

    def test_detects_bicep_from_bicep_files(self, tmp_path: Path) -> None:
        """Test Bicep detected from .bicep files using glob pattern."""
        (tmp_path / "main.bicep").write_text("param location string\n")

        detected = LanguageDetector(project_root=tmp_path).detect()

        assert Language.bicep in detected
        assert LanguageDetector(project_root=tmp_path).has_language(Language.bicep)

    def test_detects_bicep_in_subdirectory(self, tmp_path: Path) -> None:
        """Test Bicep detected from .bicep files in subdirectories."""
        infra_dir = tmp_path / "infra"
        infra_dir.mkdir()
        (infra_dir / "storage.bicep").write_text("resource storage 'Microsoft.Storage'\n")

        assert Language.bicep in LanguageDetector(project_root=tmp_path).detect()

    def test_detects_multiple_languages(self, tmp_path: Path) -> None:
        """Test multiple languages detected simultaneously."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        (tmp_path / "go.mod").write_text("module example.com/test\n")

        detected = LanguageDetector(project_root=tmp_path).detect()

        assert detected == {Language.python, Language.javascript, Language.go}

    def test_returns_empty_set_when_no_markers(self, tmp_path: Path) -> None:
        """Test empty set returned when no marker files exist."""
        (tmp_path / "Makefile").write_text("all:\n\techo hello\n")

        assert LanguageDetector(project_root=tmp_path).detect() == set()


class TestDetectLanguagesFunction:
    """Tests for the detect_languages convenience function."""

    def test_detect_languages_works(self, tmp_path: Path) -> None:
        """Test detect_languages convenience function."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detected = detect_languages(tmp_path)

        assert detected == {Language.python, Language.rust}
