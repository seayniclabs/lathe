"""Path validation and security utilities for Lathe MCP server.

All file paths are validated against a working directory to prevent
path traversal attacks. External dependency availability is checked
gracefully so the server can report what it can and cannot do.
"""

import os
import shutil
from pathlib import Path


class PathSecurityError(Exception):
    """Raised when a file path fails security validation."""


def validate_input_path(path: str, working_dir: str) -> Path:
    """Resolve and validate an input file path.

    Ensures the path:
    - Resolves to a location within working_dir
    - Does not use symlinks to escape working_dir
    - Actually exists and is a file

    Args:
        path: The file path to validate.
        working_dir: The allowed root directory.

    Returns:
        Resolved absolute Path.

    Raises:
        PathSecurityError: If the path is invalid or escapes working_dir.
        FileNotFoundError: If the file does not exist.
    """
    work = Path(working_dir).resolve()
    resolved = Path(path).resolve()

    # Check for symlink escape: resolve the path and ensure it's within working_dir
    if not str(resolved).startswith(str(work) + os.sep) and resolved != work:
        raise PathSecurityError(
            f"Path escapes working directory: {path}"
        )

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not resolved.is_file():
        raise PathSecurityError(f"Not a file: {path}")

    return resolved


def validate_output_path(path: str, working_dir: str) -> Path:
    """Resolve and validate an output file path.

    Ensures the resolved output path is within working_dir.
    Creates parent directories if they don't exist.

    Args:
        path: The output file path to validate.
        working_dir: The allowed root directory.

    Returns:
        Resolved absolute Path.

    Raises:
        PathSecurityError: If the path escapes working_dir.
    """
    work = Path(working_dir).resolve()
    resolved = Path(path).resolve()

    if not str(resolved).startswith(str(work) + os.sep) and resolved != work:
        raise PathSecurityError(
            f"Output path escapes working directory: {path}"
        )

    # Create parent directories
    resolved.parent.mkdir(parents=True, exist_ok=True)

    return resolved


def check_file_size(path: Path, max_mb: int = 500) -> None:
    """Check that a file does not exceed the size limit.

    Args:
        path: Path to the file.
        max_mb: Maximum allowed size in megabytes.

    Raises:
        ValueError: If the file exceeds the limit.
    """
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(
            f"File too large: {size_mb:.1f}MB exceeds {max_mb}MB limit"
        )


def check_dependency(name: str) -> bool:
    """Check if an external dependency binary is available on PATH.

    Args:
        name: Binary name (ffmpeg, tesseract, gs).

    Returns:
        True if the binary is found.
    """
    return shutil.which(name) is not None


def get_dependency_status() -> dict:
    """Return status and install instructions for all external dependencies.

    Returns:
        Dict mapping dependency name to status dict with 'available' bool
        and 'install_hint' string.
    """
    deps = {
        "ffmpeg": {
            "available": check_dependency("ffmpeg"),
            "install_hint": "brew install ffmpeg (macOS) / apt install ffmpeg (Debian)",
        },
        "tesseract": {
            "available": check_dependency("tesseract"),
            "install_hint": "brew install tesseract (macOS) / apt install tesseract-ocr (Debian)",
        },
        "ghostscript": {
            "available": check_dependency("gs"),
            "install_hint": "brew install ghostscript (macOS) / apt install ghostscript (Debian)",
        },
    }
    return deps
