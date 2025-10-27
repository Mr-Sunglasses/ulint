"""
File system utilities.

This module provides utility functions for file system operations
used by the linter.
"""

from __future__ import annotations

from pathlib import Path

from ..core.models import FileEntry


def file_exists(file_path: Path) -> bool:
    """
    Check if a file exists.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file exists, False otherwise
    """
    return file_path.exists() and file_path.is_file()


def directory_exists(dir_path: Path) -> bool:
    """
    Check if a directory exists.
    
    Args:
        dir_path: Path to the directory
        
    Returns:
        True if the directory exists, False otherwise
    """
    return dir_path.exists() and dir_path.is_dir()


def get_directory_files(directory: Path, relative_to: Path | None = None) -> list[FileEntry]:
    """
    Recursively get all files and directories in a directory.
    
    Args:
        directory: Directory to scan
        relative_to: Optional base path for relative paths
        
    Returns:
        List of file entries
    """
    entries = []
    relative_to = relative_to or directory

    try:
        for item in directory.rglob("*"):
            if item.is_file() or item.is_dir():
                # Get relative path
                try:
                    relative_path = item.relative_to(relative_to)
                except ValueError:
                    # If we can't get relative path, use absolute
                    relative_path = item

                entry = FileEntry(
                    path=str(relative_path),
                    type="file" if item.is_file() else "directory",
                )
                entries.append(entry)
    except (OSError, PermissionError):
        # Handle permission errors or other filesystem issues
        pass

    return entries


def read_file_safely(file_path: Path, encoding: str = "utf-8") -> str | None:
    """
    Safely read a file with error handling.
    
    Args:
        file_path: Path to the file
        encoding: File encoding
        
    Returns:
        File content as string, or None if reading failed
    """
    try:
        with open(file_path, encoding=encoding) as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def write_file_safely(file_path: Path, content: str, encoding: str = "utf-8") -> bool:
    """
    Safely write content to a file.
    
    Args:
        file_path: Path to the file
        content: Content to write
        encoding: File encoding
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return True
    except OSError:
        return False


def get_file_size(file_path: Path) -> int:
    """
    Get file size in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    try:
        return file_path.stat().st_size
    except OSError:
        return 0


def is_empty_directory(dir_path: Path) -> bool:
    """
    Check if a directory is empty.
    
    Args:
        dir_path: Path to the directory
        
    Returns:
        True if directory is empty, False otherwise
    """
    try:
        return not any(dir_path.iterdir())
    except (OSError, PermissionError):
        return False


def find_files_by_pattern(directory: Path, pattern: str) -> list[Path]:
    """
    Find files matching a pattern in a directory.
    
    Args:
        directory: Directory to search
        pattern: File pattern (e.g., "*.yml", "*.yaml")
        
    Returns:
        List of matching file paths
    """
    matches = []
    try:
        for file_path in directory.rglob(pattern):
            if file_path.is_file():
                matches.append(file_path)
    except (OSError, PermissionError):
        pass

    return matches


def get_relative_path(file_path: Path, base_path: Path) -> str:
    """
    Get relative path from base path.
    
    Args:
        file_path: File path
        base_path: Base path
        
    Returns:
        Relative path as string
    """
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        return str(file_path)
