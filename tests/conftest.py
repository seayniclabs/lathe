"""Lathe MCP server test fixtures.

Provides test fixture files and dependency detection helpers.
Fixture files are generated at session start when missing (they are gitignored).
PDF fixtures are generated programmatically via pypdf.

NOTE: The LATHE_LICENSE_KEY env var is set here so that existing tests
run in licensed mode (all tools registered). License-specific tests
handle their own env manipulation.
"""

import os
import shutil
from pathlib import Path

import pytest

# Ensure all tests run in licensed mode by default so paid tools are available.
# This must happen before any lathe module is imported at the module level.
os.environ.setdefault("LATHE_LICENSE_KEY", "SL-TEST-0000")

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


def _make_pdf(path: Path, text: str, title: str | None = None) -> Path:
    """Create a minimal single-page PDF with text content.

    Uses pypdf's add_blank_page then injects a content stream with text.
    """
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    # Add Helvetica font resource
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")

    if "/Resources" not in page:
        page[NameObject("/Resources")] = DictionaryObject()
    resources = page["/Resources"]
    if "/Font" not in resources:
        resources[NameObject("/Font")] = DictionaryObject()
    resources["/Font"][NameObject("/F1")] = writer._add_object(font)

    # Content stream with text
    stream = DecodedStreamObject()
    # Escape parentheses in PDF text string
    safe_text = text.replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)

    if title:
        writer.add_metadata({"/Title": title, "/Author": "Lathe Tests"})

    with open(path, "wb") as f:
        writer.write(f)

    return path


@pytest.fixture
def sample_pdf(tmp_path):
    """Generate a simple single-page PDF with text content."""
    return _make_pdf(
        tmp_path / "sample.pdf",
        text="Hello from Lathe PDF test",
        title="Test PDF",
    )


@pytest.fixture
def two_sample_pdfs(tmp_path):
    """Generate two simple PDFs for merge testing."""
    return [
        _make_pdf(tmp_path / "doc1.pdf", text="Document 1"),
        _make_pdf(tmp_path / "doc2.pdf", text="Document 2"),
    ]


def pytest_sessionstart(session):
    """Generate the gitignored media fixtures on a clean checkout."""
    needed = ("image_rgb.png", "image_exif.jpg", "text_image.png", "audio.wav")
    if not all((FIXTURES_DIR / name).exists() for name in needed):
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from generate_fixtures import generate

        generate()


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
