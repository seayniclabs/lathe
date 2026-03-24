"""PDF processing operations.

Uses pypdf for text extraction, merge, and metadata.
Uses ghostscript subprocess for PDF-to-image rendering.
Falls back to tesseract OCR when PDF has no text layer.
"""

import subprocess
from pathlib import Path

from .security import check_dependency


def _require_pypdf():
    """Import and return pypdf, raising a clear error if missing."""
    try:
        import pypdf
        return pypdf
    except ImportError:
        raise RuntimeError(
            "pypdf is required for PDF operations. "
            "Install with: pip install lathe-mcp[full]"
        )


def get_info(input_path: Path) -> dict:
    """Extract PDF metadata: page count, file size, title, author, etc."""
    pypdf = _require_pypdf()

    with open(input_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        meta = reader.metadata

        info = {
            "page_count": len(reader.pages),
            "file_size": input_path.stat().st_size,
            "encrypted": reader.is_encrypted,
            "title": meta.get("/Title") if meta else None,
            "author": meta.get("/Author") if meta else None,
            "creator": meta.get("/Creator") if meta else None,
        }

    return info


def extract_text(input_path: Path, pages: str | None = None) -> dict:
    """Extract text from PDF pages.

    Falls back to tesseract OCR if no text layer is found.

    Args:
        input_path: Path to the PDF file.
        pages: Optional page range like "1-3" or "2". 1-indexed.

    Returns:
        Dict with extracted text and method used.
    """
    pypdf = _require_pypdf()

    with open(input_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        total_pages = len(reader.pages)

        # Parse page range
        page_indices = _parse_page_range(pages, total_pages)

        text_parts = []
        for idx in page_indices:
            page_text = reader.pages[idx].extract_text() or ""
            text_parts.append(page_text)

    full_text = "\n\n".join(text_parts).strip()

    # If no text found, try OCR fallback
    if not full_text and check_dependency("tesseract"):
        return _ocr_fallback(input_path, page_indices)

    return {
        "text": full_text,
        "pages_extracted": [i + 1 for i in page_indices],
        "method": "text_layer" if full_text else "no_text_found",
        "char_count": len(full_text),
    }


def merge(input_paths: list[Path], output_path: Path) -> dict:
    """Merge multiple PDF files into one."""
    pypdf = _require_pypdf()

    writer = pypdf.PdfWriter()
    total_pages = 0

    for pdf_path in input_paths:
        reader = pypdf.PdfReader(pdf_path)
        total_pages += len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)

    with open(output_path, "wb") as out:
        writer.write(out)

    return {
        "input_count": len(input_paths),
        "total_pages": total_pages,
        "output_path": str(output_path),
        "output_size": output_path.stat().st_size,
    }


def to_images(
    input_path: Path,
    output_dir: Path,
    pages: str | None = None,
    fmt: str = "png",
) -> dict:
    """Convert PDF pages to images using ghostscript.

    Args:
        input_path: Path to the PDF.
        output_dir: Directory for output images.
        pages: Optional page range like "1-3".
        fmt: Output format (png or jpeg).

    Returns:
        Dict with list of output image paths.
    """
    if not check_dependency("gs"):
        raise RuntimeError(
            "Ghostscript is required for PDF-to-image conversion. "
            "Install with: brew install ghostscript (macOS) / apt install ghostscript (Debian)"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    device = "png16m" if fmt == "png" else "jpeg"
    output_pattern = str(output_dir / f"page_%03d.{fmt}")

    cmd = [
        "gs",
        "-dBATCH",
        "-dNOPAUSE",
        "-dSAFER",
        "-sDEVICE=" + device,
        "-r150",
        "-sOutputFile=" + output_pattern,
    ]

    # Add page range if specified
    if pages:
        pypdf = _require_pypdf()
        with open(input_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            total = len(reader.pages)
        indices = _parse_page_range(pages, total)
        first = min(indices) + 1
        last = max(indices) + 1
        cmd.extend([f"-dFirstPage={first}", f"-dLastPage={last}"])

    cmd.append(str(input_path))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript failed: {result.stderr}")

    # Collect output files
    output_files = sorted(output_dir.glob(f"page_*.{fmt}"))

    return {
        "output_dir": str(output_dir),
        "images": [str(f) for f in output_files],
        "count": len(output_files),
        "format": fmt,
    }


def _parse_page_range(pages: str | None, total: int) -> list[int]:
    """Parse a page range string into 0-indexed page indices.

    Args:
        pages: Range string like "1-3", "2", or None for all.
        total: Total number of pages.

    Returns:
        List of 0-indexed page indices.
    """
    if pages is None:
        return list(range(total))

    pages = pages.strip()
    if "-" in pages:
        parts = pages.split("-", 1)
        start = int(parts[0]) - 1
        end = int(parts[1])
        return list(range(max(0, start), min(end, total)))
    else:
        idx = int(pages) - 1
        if 0 <= idx < total:
            return [idx]
        raise ValueError(f"Page {pages} out of range (1-{total})")


def _ocr_fallback(input_path: Path, page_indices: list[int]) -> dict:
    """Attempt OCR on PDF pages when no text layer exists."""
    # This requires ghostscript to render pages, then tesseract to OCR them
    if not check_dependency("gs"):
        return {
            "text": "",
            "pages_extracted": [i + 1 for i in page_indices],
            "method": "ocr_unavailable_no_ghostscript",
            "char_count": 0,
        }

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Render pages
        try:
            to_images(input_path, tmp_path, fmt="png")
        except RuntimeError:
            return {
                "text": "",
                "pages_extracted": [i + 1 for i in page_indices],
                "method": "ocr_render_failed",
                "char_count": 0,
            }

        # OCR each rendered page
        text_parts = []
        for img_file in sorted(tmp_path.glob("page_*.png")):
            result = subprocess.run(
                ["tesseract", str(img_file), "stdout"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                text_parts.append(result.stdout.strip())

    full_text = "\n\n".join(text_parts).strip()
    return {
        "text": full_text,
        "pages_extracted": [i + 1 for i in page_indices],
        "method": "ocr_tesseract",
        "char_count": len(full_text),
    }
