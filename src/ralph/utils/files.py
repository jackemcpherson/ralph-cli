"""File operation utilities for Ralph CLI."""

from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    """Create directory and all parent directories if they don't exist.

    Args:
        path: Path to the directory to create.

    Returns:
        The Path object for the created directory.
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def read_file(path: Path | str, encoding: str = "utf-8") -> str:
    """Read entire file contents as a string.

    Args:
        path: Path to the file to read.
        encoding: Character encoding to use (default: utf-8).

    Returns:
        The file contents as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read due to permissions.
    """
    return Path(path).read_text(encoding=encoding)


def write_file(path: Path | str, content: str, encoding: str = "utf-8") -> None:
    """Write content to a file, creating parent directories if needed.

    Args:
        path: Path to the file to write.
        content: Content to write to the file.
        encoding: Character encoding to use (default: utf-8).
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=encoding)


def append_file(path: Path | str, content: str, encoding: str = "utf-8") -> None:
    """Append content to a file, creating it if it doesn't exist.

    Args:
        path: Path to the file to append to.
        content: Content to append to the file.
        encoding: Character encoding to use (default: utf-8).
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding=encoding) as f:
        f.write(content)


def file_exists(path: Path | str) -> bool:
    """Check if a file exists.

    Args:
        path: Path to check.

    Returns:
        True if the path exists and is a file, False otherwise.
    """
    return Path(path).is_file()


def get_project_root() -> Path:
    """Find the project root directory.

    Walks up the directory tree from the current working directory
    looking for common project markers (pyproject.toml, package.json,
    go.mod, Cargo.toml, CLAUDE.md, .git).

    Returns:
        Path to the project root directory, or current working directory
        if no project markers are found.
    """
    markers = [
        "pyproject.toml",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "CLAUDE.md",
        ".git",
    ]

    current = Path.cwd()

    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    # Fallback to current working directory if no markers found
    return Path.cwd()
