"""PDF tools: metadata, text (with OCR fallback), merge, and page rendering.

Uses pypdf (the ``pdf`` extra) for reading and merging, and ghostscript for
rendering pages to images. Text extraction falls back to OCR when a page has no
text layer and the OCR pieces are installed.

Note: no ``from __future__ import annotations`` here (see images.py).
"""

import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from ..errors import LatheError
from ..paths import atomic_write, resolve_dir
from . import (GHOSTSCRIPT, PYPDF, PYTESSERACT, TESSERACT, Module, Setting, ToolSpec, READ, WRITE,
               parse_pages, window)

OCR_PAGE_LIMIT = 50
RENDER_TIMEOUT = 300


class PdfInfo(BaseModel):
    page_count: int | None = Field(description="None when the PDF is encrypted and cannot be opened without a password.")
    file_bytes: int
    encrypted: bool
    title: str | None = None
    author: str | None = None
    creator: str | None = None


class PdfText(BaseModel):
    text: str
    method: str = Field(description="text_layer, ocr, no_text_found or ocr_unavailable.")
    pages: list[int]
    total_chars: int
    offset: int
    returned_chars: int
    next_offset: int | None = Field(description="Pass as offset to read the next part. None at the end.")
    note: str | None = None


class PdfMerge(BaseModel):
    output_path: str
    output_bytes: int
    input_count: int
    total_pages: int


class PdfImages(BaseModel):
    output_dir: str
    images: list[str]
    count: int
    format: str
    dpi: int


def _reader(path: Path, allow_encrypted: bool = False):
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
    except Exception:
        raise LatheError("pdf", "unreadable", f"{path.name} is not a PDF Lathe can read.",
                         "check the file is a complete PDF.")
    if reader.is_encrypted and not reader.decrypt("") and not allow_encrypted:
        raise LatheError("pdf", "encrypted", f"{path.name} is password-protected.",
                         "remove the password first, then process the unlocked copy.")
    return reader


def _render(src: Path, first: int, last: int, out_dir: Path, fmt: str, dpi: int) -> list[Path]:
    """Render pages first..last (1-indexed) to out_dir with ghostscript. Returns the files in page order."""
    ext = "jpeg" if fmt == "jpeg" else "png"
    device = "jpeg" if ext == "jpeg" else "png16m"
    cmd = [
        "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
        f"-sDEVICE={device}", f"-r{dpi}",
        f"-dFirstPage={first}", f"-dLastPage={last}",
        f"-sOutputFile={out_dir / f'page_%03d.{ext}'}",
        str(src),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise LatheError("pdf", "failed", f"ghostscript could not render the pages: {result.stderr[-300:]}")
    return sorted(out_dir.glob(f"page_*.{ext}"))


def _ocr_pages(src: Path, idx: list[int]) -> tuple[str, str, str | None]:
    missing = [r for r in (GHOSTSCRIPT, PYTESSERACT, TESSERACT) if not r.available()]
    if missing:
        fix = " && ".join(dict.fromkeys(r.install for r in missing))
        return "", "ocr_unavailable", f"no text layer, and OCR is not set up. Run: {fix}"
    from .ocr import recognize_image

    capped = idx[:OCR_PAGE_LIMIT]
    with tempfile.TemporaryDirectory(prefix="lathe-ocr-") as tmp:
        files = _render(src, capped[0] + 1, capped[-1] + 1, Path(tmp), "png", 200)
        texts = [recognize_image(f, None) for f in files]
    note = None if len(idx) <= OCR_PAGE_LIMIT else f"OCR read the first {OCR_PAGE_LIMIT} of {len(idx)} pages."
    return "\n\n".join(t for t in texts if t).strip(), "ocr", note


_TOOLS = (
    ToolSpec("pdf_info", "PDF metadata: page count, file size, encryption, title, author and creator.",
             requires=(PYPDF,)),
    ToolSpec("pdf_extract_text", "Extract text from a PDF, or from some pages (\"2-5\"). Pages with no text layer are "
             "read with OCR when it is installed. Long text comes in parts: pass next_offset as offset to continue.",
             requires=(PYPDF,)),
    ToolSpec("pdf_merge", "Merge several PDFs, in the order given, into one new PDF.",
             requires=(PYPDF,), annotations=WRITE),
    ToolSpec("pdf_to_images", "Render PDF pages to PNG or JPEG files in a folder, at a chosen DPI. Needs ghostscript.",
             requires=(PYPDF, GHOSTSCRIPT), annotations=WRITE),
)


class PdfModule(Module):
    name = "pdf"
    summary = "PDF files: info, text extraction (with OCR fallback), merge, render pages to images."
    settings: tuple[Setting, ...] = ()
    tools = _TOOLS

    def register(self, mcp, config) -> None:
        self.config = config
        tool = self.tool

        @tool(mcp, "pdf_info")
        def pdf_info(input_path: str) -> PdfInfo:
            src = self.input_file(input_path)
            reader = _reader(src, allow_encrypted=True)
            encrypted = bool(reader.is_encrypted)
            if encrypted:
                return PdfInfo(page_count=None, file_bytes=src.stat().st_size, encrypted=True)
            meta = reader.metadata

            def field(key):
                value = meta.get(key) if meta else None
                return str(value) if value else None
            return PdfInfo(page_count=len(reader.pages), file_bytes=src.stat().st_size, encrypted=False,
                           title=field("/Title"), author=field("/Author"), creator=field("/Creator"))

        @tool(mcp, "pdf_extract_text")
        def pdf_extract_text(input_path: str, pages: str | None = None,
                             offset: Annotated[int, Field(ge=0)] = 0,
                             max_chars: Annotated[int, Field(ge=1, le=200_000)] = 20_000,
                             ocr_fallback: bool = True) -> PdfText:
            src = self.input_file(input_path)
            reader = _reader(src)
            total = len(reader.pages)
            idx = parse_pages(pages, total) if pages else list(range(total))
            text = "\n\n".join((reader.pages[i].extract_text() or "").strip() for i in idx).strip()
            method, note = ("text_layer", None) if text else ("no_text_found", None)
            if not text and ocr_fallback:
                text, method, note = _ocr_pages(src, idx)
            chunk, next_offset = window(text, offset, max_chars)
            return PdfText(text=chunk, method=method, pages=[i + 1 for i in idx], total_chars=len(text),
                           offset=offset, returned_chars=len(chunk), next_offset=next_offset, note=note)

        @tool(mcp, "pdf_merge")
        def pdf_merge(input_paths: list[str], output_path: str, overwrite: bool = False) -> PdfMerge:
            if not 1 <= len(input_paths) <= 200:
                raise LatheError("pdf", "bad_input", f"merge takes 1 to 200 files, got {len(input_paths)}.",
                                 "pass the PDFs in the order you want them.")
            from pypdf import PdfWriter

            sources = [self.input_file(p) for p in input_paths]
            out = self.output_file(output_path, overwrite, inputs=sources)
            writer = PdfWriter()
            total = 0
            for src in sources:
                reader = _reader(src)
                total += len(reader.pages)
                writer.append(reader)

            def write(tmp: Path) -> None:
                writer.write(str(tmp))
                writer.close()

            atomic_write(out, write)
            return PdfMerge(output_path=str(out), output_bytes=out.stat().st_size,
                            input_count=len(sources), total_pages=total)

        @tool(mcp, "pdf_to_images")
        def pdf_to_images(input_path: str, output_dir: str, pages: str | None = None,
                          format: Literal["png", "jpeg"] = "png",
                          dpi: Annotated[int, Field(ge=72, le=600)] = 150,
                          overwrite: bool = False) -> PdfImages:
            src = self.input_file(input_path)
            reader = _reader(src)
            total = len(reader.pages)
            idx = parse_pages(pages, total) if pages else list(range(total))
            dest = resolve_dir(output_dir, self.config.working_dir())
            if dest.exists() and not dest.is_dir():
                raise LatheError("core", "not_a_file", f"{output_dir!r} is a file, not a folder.", "give a folder name.")
            dest.mkdir(parents=True, exist_ok=True)
            staging = dest / f".lathe-{uuid.uuid4().hex[:8]}"
            staging.mkdir()
            try:
                rendered = _render(src, idx[0] + 1, idx[-1] + 1, staging, format, dpi)
                clashes = [f.name for f in rendered if (dest / f.name).exists()]
                if clashes and not overwrite:
                    raise LatheError("core", "exists", f"{', '.join(clashes[:3])} already exist in {output_dir!r}.",
                                     "pass overwrite=true to replace them, or use an empty folder.")
                images = []
                for f in rendered:
                    target = dest / f.name
                    f.replace(target)
                    images.append(str(target))
            finally:
                for f in staging.glob("*"):
                    f.unlink()
                staging.rmdir()
            return PdfImages(output_dir=str(dest), images=images, count=len(images), format=format, dpi=dpi)
