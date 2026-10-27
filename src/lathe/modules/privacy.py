"""scrub_metadata: find and remove location and author metadata from images and PDFs.

``inspect`` (the default) only reads the file and lists what it holds. ``scrub`` writes one
new file and never overwrites an existing one unless overwrite=true. Images: all EXIF
(including GPS), ICC and XMP data is removed, and the picture is turned upright first so
the orientation tag can go. PDFs: Author, Creator and Producer are removed, along with the
XMP metadata stream; Title, Subject, Keywords and dates are kept and listed.

Note: no ``from __future__ import annotations`` here (see images.py).
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..errors import LatheError
from ..paths import atomic_write
from . import PYPDF, Module, Requirement, Setting, ToolSpec, WRITE, relpath
from . import images as img
from . import pdf as pdf_mod

PDF_REMOVE = ("/Author", "/Creator", "/Producer")
MAX_VALUE = 200


class MetadataField(BaseModel):
    name: str
    value: str = Field(description="Up to 200 characters. Binary data is shown as its length.")


class ScrubResult(BaseModel):
    kind: str = Field(description="image or pdf")
    mode: str
    found: list[MetadataField]
    gps_present: bool = Field(description="True when the image carries GPS coordinates.")
    removed: list[str] = Field(default_factory=list, description="Field names removed by scrub mode.")
    kept: list[str] = Field(default_factory=list, description="Field names kept by scrub mode.")
    output_path: str | None = None
    output_bytes: int | None = None
    note: str | None = None


def _field(name: str, value) -> MetadataField:
    text = str(value)
    return MetadataField(name=name, value=text[:MAX_VALUE] if len(text) <= MAX_VALUE else text[:MAX_VALUE] + "...")


def _image_found(image) -> list[MetadataField]:
    exif, _ = img._exif_summary(image)
    found = [_field(k, v) for k, v in exif.items()]
    if image.info.get("icc_profile"):
        found.append(MetadataField(name="ICC profile", value=f"<{len(image.info['icc_profile'])} bytes>"))
    if any(k in image.info for k in ("xmp", "XML:com.adobe.xmp")):
        found.append(MetadataField(name="XMP", value="<present>"))
    if image.info.get("comment"):
        found.append(_field("Comment", image.info["comment"]))
    return found


def _pdf_found(reader) -> list[MetadataField]:
    found = [_field(str(k).lstrip("/"), v) for k, v in (reader.metadata or {}).items()]
    try:
        xmp = reader.trailer["/Root"].get_object().get("/Metadata")
        if xmp is not None:
            found.append(MetadataField(name="XMP metadata", value=f"<{len(xmp.get_object().get_data())} bytes>"))
    except Exception:
        pass
    return found


def _gps(found: list[MetadataField]) -> bool:
    return any(f.name == "GPSInfo" or f.name.startswith("GPS") for f in found)


def _clean_pdf(src: Path):
    """A writer holding the PDF with Author, Creator, Producer and the XMP stream removed."""
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=pdf_mod._reader(src))
    info = getattr(writer, "_info", None)  # pypdf keeps the document info dictionary here
    if info is not None:
        info = info.get_object()
        for key in PDF_REMOVE:
            if key in info:
                del info[key]
    catalog = writer.root_object
    if "/Metadata" in catalog:
        del catalog["/Metadata"]
    return writer


class PrivacyModule(Module):
    name = "privacy"
    summary = "Find and remove location and author metadata from images and PDFs, writing a new file. Inspect first."
    settings: tuple[Setting, ...] = ()
    default_enabled = False
    tools = (
        ToolSpec("scrub_metadata", "Inspect (default) or scrub an image or PDF. Inspect lists the metadata and whether "
                 "the image has GPS coordinates; it writes nothing. Scrub writes one new file without the metadata and "
                 "reports what was removed. Never overwrites unless overwrite=true.",
                 annotations=WRITE),
    )

    @property
    def requirements(self) -> list[Requirement]:
        return [PYPDF]

    def register(self, mcp, config) -> None:
        self.config = config
        tool = self.tool

        @tool(mcp, "scrub_metadata")
        def scrub_metadata(input_path: str, mode: Literal["inspect", "scrub"] = "inspect",
                           output_path: str | None = None, overwrite: bool = False) -> ScrubResult:
            src = self.input_file(input_path)
            root = self.config.working_dir()
            is_pdf = src.suffix.lower() == ".pdf"
            if is_pdf:
                self.need(PYPDF)
                found = _pdf_found(pdf_mod._reader(src, allow_encrypted=False))
                kind = "pdf"
            else:
                with img._open(src, load=False) as image:
                    found = _image_found(image)
                kind = "image"
            gps = _gps(found)

            if mode == "inspect":
                return ScrubResult(kind=kind, mode=mode, found=found, gps_present=gps,
                                   note="Inspect only: nothing was written. Call with mode=scrub and output_path to make a clean copy.")

            if not output_path:
                raise LatheError("privacy", "bad_input", "mode=scrub needs output_path.",
                                 "give a new file name for the clean copy.")
            out = self.output_file(output_path, overwrite, inputs=[src])
            if is_pdf:
                names_removed = {k.lstrip("/") for k in PDF_REMOVE} | {"XMP metadata"}
                removed = [f.name for f in found if f.name in names_removed]
                kept = [f.name for f in found if f.name not in names_removed]
                writer = _clean_pdf(src)

                def write(tmp: Path) -> None:
                    writer.write(str(tmp))
                    writer.close()

                atomic_write(out, write)
            else:
                removed = [f.name for f in found]
                kept = []
                with img._open(src) as raw:
                    upright, _ = img._upright(raw)
                    fmt = img._format_for(out)
                    clean = img._for_format(upright, fmt).copy()
                    clean.info = {}
                    kwargs = {"quality": 95} if fmt in ("JPEG", "WEBP", "AVIF") else {}
                    img._save(clean, out, fmt, **kwargs)

            return ScrubResult(kind=kind, mode=mode, found=found, gps_present=gps, removed=removed, kept=kept,
                               output_path=relpath(out, root), output_bytes=out.stat().st_size)
