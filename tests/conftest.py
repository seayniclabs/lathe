"""Lathe MCP server test fixtures.

Provides test fixture files and dependency detection helpers.
Fixture files are small (<5MB total) and committed to the repo.
"""

import os
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory for tool results."""
    return tmp_path


@pytest.fixture
def has_ffmpeg():
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


@pytest.fixture
def has_tesseract():
    """Check if tesseract is available."""
    return shutil.which("tesseract") is not None


@pytest.fixture
def has_ghostscript():
    """Check if ghostscript is available."""
    return shutil.which("gs") is not None


def pytest_collection_modifyitems(config, items):
    """Skip tests that require missing external dependencies."""
    for item in items:
        if "requires_ffmpeg" in item.keywords and not shutil.which("ffmpeg"):
            item.add_marker(
                pytest.mark.skip(reason="ffmpeg not installed")
            )
        if "requires_tesseract" in item.keywords and not shutil.which("tesseract"):
            item.add_marker(
                pytest.mark.skip(reason="tesseract not installed")
            )
        if "requires_ghostscript" in item.keywords and not shutil.which("gs"):
            item.add_marker(
                pytest.mark.skip(reason="ghostscript not installed")
            )
