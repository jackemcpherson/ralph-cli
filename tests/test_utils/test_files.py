"""Tests for file utilities."""

import os
from pathlib import Path

import pytest

from ralph.utils.files import (
    append_file,
    ensure_dir,
    file_exists,
    get_project_root,
    read_file,
    write_file,
)


class TestEnsureDir:
    """Tests for ensure_dir function."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Test that ensure_dir creates a directory."""
        new_dir = tmp_path / "new_directory"
        assert not new_dir.exists()

        result = ensure_dir(new_dir)

        assert result == new_dir
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Test that ensure_dir creates nested directories."""
        nested_dir = tmp_path / "level1" / "level2" / "level3"

        result = ensure_dir(nested_dir)

        assert result == nested_dir
        assert nested_dir.exists()

    def test_returns_existing_directory(self, tmp_path: Path) -> None:
        """Test that ensure_dir returns existing directory without error."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        result = ensure_dir(existing_dir)

        assert result == existing_dir
        assert existing_dir.exists()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test that ensure_dir accepts string paths."""
        str_path = str(tmp_path / "string_path")

        result = ensure_dir(str_path)

        assert result == Path(str_path)
        assert Path(str_path).exists()


class TestReadFile:
    """Tests for read_file function."""

    def test_reads_file_content(self, tmp_path: Path) -> None:
        """Test that read_file returns file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = read_file(test_file)

        assert result == "Hello, World!"

    def test_reads_utf8_content(self, tmp_path: Path) -> None:
        """Test that read_file handles UTF-8 encoding."""
        test_file = tmp_path / "unicode.txt"
        test_file.write_text("Hello \u4e16\u754c \U0001f30d", encoding="utf-8")

        result = read_file(test_file)

        assert result == "Hello \u4e16\u754c \U0001f30d"

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        """Test that read_file raises FileNotFoundError for missing file."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            read_file(nonexistent)

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test that read_file accepts string paths."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content")

        result = read_file(str(test_file))

        assert result == "Content"

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """Test that read_file uses custom encoding."""
        test_file = tmp_path / "latin1.txt"
        test_file.write_bytes(b"Caf\xe9")

        result = read_file(test_file, encoding="latin-1")

        assert result == "Caf\xe9"


class TestWriteFile:
    """Tests for write_file function."""

    def test_writes_content_to_file(self, tmp_path: Path) -> None:
        """Test that write_file creates file with content."""
        test_file = tmp_path / "output.txt"

        write_file(test_file, "Test content")

        assert test_file.exists()
        assert test_file.read_text() == "Test content"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that write_file creates parent directories."""
        nested_file = tmp_path / "parent" / "child" / "file.txt"

        write_file(nested_file, "Nested content")

        assert nested_file.exists()
        assert nested_file.read_text() == "Nested content"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that write_file overwrites existing content."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Old content")

        write_file(test_file, "New content")

        assert test_file.read_text() == "New content"

    def test_writes_utf8_content(self, tmp_path: Path) -> None:
        """Test that write_file handles UTF-8 encoding."""
        test_file = tmp_path / "unicode.txt"

        write_file(test_file, "Hello \u4e16\u754c \U0001f30d")

        assert test_file.read_text(encoding="utf-8") == "Hello \u4e16\u754c \U0001f30d"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test that write_file accepts string paths."""
        test_file = str(tmp_path / "string_path.txt")

        write_file(test_file, "Content")

        assert Path(test_file).read_text() == "Content"


class TestAppendFile:
    """Tests for append_file function."""

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        """Test that append_file adds content to existing file."""
        test_file = tmp_path / "log.txt"
        test_file.write_text("Line 1\n")

        append_file(test_file, "Line 2\n")

        assert test_file.read_text() == "Line 1\nLine 2\n"

    def test_creates_file_if_not_exists(self, tmp_path: Path) -> None:
        """Test that append_file creates file if it doesn't exist."""
        test_file = tmp_path / "new_log.txt"

        append_file(test_file, "First entry\n")

        assert test_file.exists()
        assert test_file.read_text() == "First entry\n"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that append_file creates parent directories."""
        nested_file = tmp_path / "logs" / "app" / "debug.log"

        append_file(nested_file, "Debug message\n")

        assert nested_file.exists()

    def test_multiple_appends(self, tmp_path: Path) -> None:
        """Test multiple appends to same file."""
        test_file = tmp_path / "multi.txt"

        append_file(test_file, "A")
        append_file(test_file, "B")
        append_file(test_file, "C")

        assert test_file.read_text() == "ABC"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test that append_file accepts string paths."""
        test_file = str(tmp_path / "string.txt")

        append_file(test_file, "Content")

        assert Path(test_file).read_text() == "Content"


class TestFileExists:
    """Tests for file_exists function."""

    def test_returns_true_for_existing_file(self, tmp_path: Path) -> None:
        """Test that file_exists returns True for existing file."""
        test_file = tmp_path / "exists.txt"
        test_file.write_text("Content")

        result = file_exists(test_file)

        assert result is True

    def test_returns_false_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that file_exists returns False for nonexistent file."""
        nonexistent = tmp_path / "does_not_exist.txt"

        result = file_exists(nonexistent)

        assert result is False

    def test_returns_false_for_directory(self, tmp_path: Path) -> None:
        """Test that file_exists returns False for directories."""
        test_dir = tmp_path / "directory"
        test_dir.mkdir()

        result = file_exists(test_dir)

        assert result is False

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test that file_exists accepts string paths."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("Content")

        result = file_exists(str(test_file))

        assert result is True


class TestGetProjectRoot:
    """Tests for get_project_root function."""

    def test_finds_pyproject_toml(self, tmp_path: Path) -> None:
        """Test that get_project_root finds pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        subdir = tmp_path / "src" / "package"
        subdir.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = get_project_root()
        finally:
            os.chdir(original_cwd)

        assert result == tmp_path

    def test_finds_package_json(self, tmp_path: Path) -> None:
        """Test that get_project_root finds package.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        subdir = tmp_path / "src"
        subdir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = get_project_root()
        finally:
            os.chdir(original_cwd)

        assert result == tmp_path

    def test_finds_go_mod(self, tmp_path: Path) -> None:
        """Test that get_project_root finds go.mod."""
        (tmp_path / "go.mod").write_text("module test")
        subdir = tmp_path / "cmd" / "app"
        subdir.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = get_project_root()
        finally:
            os.chdir(original_cwd)

        assert result == tmp_path

    def test_finds_cargo_toml(self, tmp_path: Path) -> None:
        """Test that get_project_root finds Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        subdir = tmp_path / "src"
        subdir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = get_project_root()
        finally:
            os.chdir(original_cwd)

        assert result == tmp_path

    def test_finds_claude_md(self, tmp_path: Path) -> None:
        """Test that get_project_root finds CLAUDE.md."""
        (tmp_path / "CLAUDE.md").write_text("# Project")
        subdir = tmp_path / "lib"
        subdir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = get_project_root()
        finally:
            os.chdir(original_cwd)

        assert result == tmp_path

    def test_finds_git_directory(self, tmp_path: Path) -> None:
        """Test that get_project_root finds .git directory."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "utils"
        subdir.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = get_project_root()
        finally:
            os.chdir(original_cwd)

        assert result == tmp_path
