"""Unit tests for language detection service.

Focused tests for language detection functionality:
- Language enum values
- Detection of Python from marker files
- Detection of JavaScript/TypeScript from marker files
- Detection of Go from marker files
- Detection of Rust from marker files
- Multiple language detection
"""

from pathlib import Path

import pytest

from ralph.services import Language, LanguageDetector, detect_languages


class TestLanguageEnum:
    """Tests for the Language enum."""

    def test_language_python_value(self) -> None:
        """Test python language has correct value."""
        assert Language.python.value == "python"

    def test_language_javascript_value(self) -> None:
        """Test javascript language has correct value."""
        assert Language.javascript.value == "javascript"

    def test_language_typescript_value(self) -> None:
        """Test typescript language has correct value."""
        assert Language.typescript.value == "typescript"

    def test_language_go_value(self) -> None:
        """Test go language has correct value."""
        assert Language.go.value == "go"

    def test_language_rust_value(self) -> None:
        """Test rust language has correct value."""
        assert Language.rust.value == "rust"

    def test_language_is_str_enum(self) -> None:
        """Test Language inherits from str and can be compared as string."""
        assert Language.python == "python"
        assert Language.javascript == "javascript"
        assert Language.typescript == "typescript"
        assert Language.go == "go"
        assert Language.rust == "rust"

    def test_language_all_values(self) -> None:
        """Test all expected enum values exist."""
        values = {lang.value for lang in Language}
        assert values == {"python", "javascript", "typescript", "go", "rust"}


class TestLanguageDetectorPython:
    """Tests for Python language detection."""

    def test_detect_python_from_pyproject_toml(self, tmp_path: Path) -> None:
        """Test Python detected from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.python in detected

    def test_detect_python_from_setup_py(self, tmp_path: Path) -> None:
        """Test Python detected from setup.py."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.python in detected

    def test_detect_python_from_requirements_txt(self, tmp_path: Path) -> None:
        """Test Python detected from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.python in detected

    def test_has_language_python(self, tmp_path: Path) -> None:
        """Test has_language returns True for detected Python."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        detector = LanguageDetector(project_root=tmp_path)

        assert detector.has_language(Language.python) is True
        assert detector.has_language(Language.go) is False


class TestLanguageDetectorJavaScript:
    """Tests for JavaScript/TypeScript language detection."""

    def test_detect_javascript_from_package_json(self, tmp_path: Path) -> None:
        """Test JavaScript detected from package.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.javascript in detected

    def test_detect_typescript_from_tsconfig_json(self, tmp_path: Path) -> None:
        """Test TypeScript detected from tsconfig.json."""
        (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}\n')

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.typescript in detected

    def test_both_js_and_ts_can_be_detected(self, tmp_path: Path) -> None:
        """Test both JavaScript and TypeScript can be detected simultaneously."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}\n')

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.javascript in detected
        assert Language.typescript in detected


class TestLanguageDetectorGo:
    """Tests for Go language detection."""

    def test_detect_go_from_go_mod(self, tmp_path: Path) -> None:
        """Test Go detected from go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test\n\ngo 1.21\n")

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.go in detected

    def test_has_language_go(self, tmp_path: Path) -> None:
        """Test has_language returns True for detected Go."""
        (tmp_path / "go.mod").write_text("module example.com/test\n")

        detector = LanguageDetector(project_root=tmp_path)

        assert detector.has_language(Language.go) is True
        assert detector.has_language(Language.rust) is False


class TestLanguageDetectorRust:
    """Tests for Rust language detection."""

    def test_detect_rust_from_cargo_toml(self, tmp_path: Path) -> None:
        """Test Rust detected from Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.rust in detected

    def test_has_language_rust(self, tmp_path: Path) -> None:
        """Test has_language returns True for detected Rust."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detector = LanguageDetector(project_root=tmp_path)

        assert detector.has_language(Language.rust) is True
        assert detector.has_language(Language.python) is False


class TestLanguageDetectorMultiple:
    """Tests for multiple language detection."""

    def test_detect_multiple_languages(self, tmp_path: Path) -> None:
        """Test multiple languages detected simultaneously."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        (tmp_path / "go.mod").write_text("module example.com/test\n")

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert Language.python in detected
        assert Language.javascript in detected
        assert Language.go in detected
        assert len(detected) == 3

    def test_detect_all_languages(self, tmp_path: Path) -> None:
        """Test all supported languages can be detected at once."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}\n')
        (tmp_path / "go.mod").write_text("module example.com/test\n")
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert detected == {
            Language.python,
            Language.javascript,
            Language.typescript,
            Language.go,
            Language.rust,
        }


class TestLanguageDetectorNoLanguages:
    """Tests for projects with no detected languages."""

    def test_detect_returns_empty_set_for_empty_directory(self, tmp_path: Path) -> None:
        """Test detection returns empty set when no marker files exist."""
        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert detected == set()
        assert len(detected) == 0

    def test_detect_ignores_unrecognized_files(self, tmp_path: Path) -> None:
        """Test detection ignores unrecognized marker files."""
        (tmp_path / "Makefile").write_text("all:\n\techo hello\n")
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.0)\n")

        detector = LanguageDetector(project_root=tmp_path)
        detected = detector.detect()

        assert detected == set()


class TestDetectLanguagesFunction:
    """Tests for the detect_languages convenience function."""

    def test_detect_languages_returns_set(self, tmp_path: Path) -> None:
        """Test detect_languages function returns a set."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        detected = detect_languages(tmp_path)

        assert isinstance(detected, set)
        assert Language.python in detected

    def test_detect_languages_empty_directory(self, tmp_path: Path) -> None:
        """Test detect_languages returns empty set for empty directory."""
        detected = detect_languages(tmp_path)

        assert detected == set()

    def test_detect_languages_multiple(self, tmp_path: Path) -> None:
        """Test detect_languages detects multiple languages."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detected = detect_languages(tmp_path)

        assert Language.python in detected
        assert Language.rust in detected
        assert len(detected) == 2


class TestLanguageDetectorModel:
    """Tests for LanguageDetector Pydantic model."""

    def test_language_detector_requires_project_root(self) -> None:
        """Test LanguageDetector requires project_root field."""
        with pytest.raises(Exception):
            LanguageDetector()  # type: ignore[call-arg]

    def test_language_detector_accepts_path(self, tmp_path: Path) -> None:
        """Test LanguageDetector accepts Path object."""
        detector = LanguageDetector(project_root=tmp_path)

        assert detector.project_root == tmp_path

    def test_language_detector_serialization(self, tmp_path: Path) -> None:
        """Test LanguageDetector can be serialized."""
        detector = LanguageDetector(project_root=tmp_path)
        data = detector.model_dump()

        assert data["project_root"] == tmp_path
