"""Image tools. Pillow ships with the base install, so this module is always available.

Note: no ``from __future__ import annotations`` here. FastMCP reads the tool
signatures at registration time, and string annotations would not resolve.
"""

from pathlib import Path

from PIL import ExifTags, Image
from typing import Annotated

from pydantic import BaseModel, Field

from ..errors import LatheError
from ..paths import atomic_write
from . import Module, Setting, ToolSpec, READ, WRITE

# Pillow's decompression-bomb guard, set explicitly so the limit is visible here.
Image.MAX_IMAGE_PIXELS = 178_956_970
MAX_PIXELS = 178_956_970
ORIENTATION = 0x0112
ALPHA_FORMATS = {"PNG", "WEBP", "AVIF"}
FORMAT_BY_EXT = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP", ".avif": "AVIF", ".bmp": "BMP"}
FORMAT_BY_NAME = {"png": "PNG", "jpeg": "JPEG", "jpg": "JPEG", "webp": "WEBP", "avif": "AVIF", "bmp": "BMP"}
TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


class ImageInfo(BaseModel):
    width: int
    height: int
    format: str | None
    mode: str
    file_bytes: int
    exif: dict[str, str] = Field(default_factory=dict, description="Up to 50 EXIF tags; values cut at 200 characters.")
    exif_truncated: bool = False


class OutputImage(BaseModel):
    output_path: str
    output_bytes: int
    width: int
    height: int
    format: str


class ResizeResult(OutputImage):
    original_size: list[int]


class ConvertResult(OutputImage):
    input_format: str | None


class OptimizeResult(OutputImage):
    original_bytes: int
    savings_percent: float


class CropResult(OutputImage):
    crop_box: list[int]


class ThumbnailResult(OutputImage):
    original_size: list[int]
    max_dimension: int


def _open(path: Path, load: bool = True) -> Image.Image:
    try:
        img = Image.open(path)
        if load:
            img.load()
        return img
    except Image.DecompressionBombError:
        raise LatheError("images", "too_large", "the image is too many pixels to process safely.",
                         "resize or crop it first with a smaller source.")
    except (Image.UnidentifiedImageError, OSError, SyntaxError):
        raise LatheError("images", "unreadable", f"{path.name} is not an image Pillow can read.",
                         "check the file, or convert it to PNG first.")


def _upright(img: Image.Image) -> tuple[Image.Image, bool]:
    """Apply the EXIF orientation. Returns the image and whether it was rotated or flipped."""
    try:
        orientation = img.getexif().get(ORIENTATION, 1)
    except Exception:
        return img, False
    op = TRANSPOSE.get(orientation)
    return (img.transpose(op), True) if op is not None else (img, False)


def _for_format(img: Image.Image, fmt: str) -> Image.Image:
    """Convert the pixel mode so the target format can store it."""
    if fmt in ALPHA_FORMATS:
        if img.mode in ("RGB", "RGBA", "L"):
            return img
        if img.mode in ("LA", "PA") or (img.mode == "P" and "transparency" in img.info):
            return img.convert("RGBA")
        return img.convert("RGB")
    if img.mode in ("RGB", "L"):
        return img
    return img.convert("RGB")


def _format_for(out: Path) -> str:
    fmt = FORMAT_BY_EXT.get(out.suffix.lower())
    if fmt is None:
        raise LatheError("images", "bad_input", f"unknown output extension {out.suffix!r}.",
                         "use .png, .jpg, .webp, .avif or .bmp.")
    return fmt


def _check_pixels(width: int, height: int) -> None:
    if width < 1 or height < 1:
        raise LatheError("images", "bad_input", "the output would have no pixels.", "use a larger size.")
    if width * height > MAX_PIXELS:
        raise LatheError("images", "too_large", f"{width}x{height} is over the pixel limit.",
                         "pick a smaller size.")


def _save(img: Image.Image, out: Path, fmt: str, **kwargs) -> dict:
    atomic_write(out, lambda tmp: img.save(tmp, format=fmt, **kwargs))
    return {"output_path": str(out), "output_bytes": out.stat().st_size,
            "width": img.width, "height": img.height, "format": fmt}


def _exif_summary(img: Image.Image, limit: int = 50) -> tuple[dict[str, str], bool]:
    try:
        exif = img.getexif()
    except Exception:
        return {}, False
    items = list(exif.items())
    out: dict[str, str] = {}
    for tag, value in items[:limit]:
        name = ExifTags.TAGS.get(tag, f"tag_{tag:#06x}")
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8").rstrip("\x00")
            except UnicodeDecodeError:
                value = f"<{len(value)} bytes>"
        out[name] = str(value)[:200]
    return out, len(items) > limit


def _target_size(w: int, h: int, width, height, percentage) -> tuple[int, int]:
    if percentage is not None:
        if width or height:
            raise LatheError("images", "bad_input", "give percentage, or width and/or height, not both.",
                             "drop one of the two.")
        if not 0 < percentage <= 1000:
            raise LatheError("images", "bad_input", "percentage must be above 0 and at most 1000.", "try 50 for half size.")
        return max(1, int(w * percentage / 100)), max(1, int(h * percentage / 100))
    if width and height:
        return width, height
    if width:
        return width, max(1, int(h * width / w))
    if height:
        return max(1, int(w * height / h)), height
    raise LatheError("images", "bad_input", "provide width, height, or percentage.", "pass one of them.")


_TOOLS = (
    ToolSpec("image_info", "Image metadata: width, height, format, mode, file size, and EXIF tags (capped)."),
    ToolSpec("image_resize", "Resize an image by width, height, or percentage. Keeps the aspect ratio when only one "
             "dimension is given. Output format comes from the output extension.", annotations=WRITE),
    ToolSpec("image_convert", "Convert an image to png, jpeg, webp, avif or bmp. The output extension must match.",
             annotations=WRITE),
    ToolSpec("image_optimize", "Shrink an image for web delivery. Metadata is stripped unless strip_metadata=false.",
             annotations=WRITE),
    ToolSpec("image_crop", "Crop a rectangle from an image. x and y are pixels from the top-left corner.",
             annotations=WRITE),
    ToolSpec("image_thumbnail", "Make a thumbnail that fits inside a square of the given size, keeping the aspect ratio.",
             annotations=WRITE),
)


class ImagesModule(Module):
    name = "images"
    summary = "Image files: info, resize, convert, optimize, crop, thumbnail. Pillow, always available."
    settings: tuple[Setting, ...] = ()
    tools = tuple(_TOOLS)

    def register(self, mcp, config) -> None:
        self.config = config
        tool = self.tool

        @tool(mcp, "image_info")
        def image_info(input_path: str) -> ImageInfo:
            src = self.input_file(input_path)
            with _open(src, load=False) as img:
                exif, truncated = _exif_summary(img)
                return ImageInfo(width=img.width, height=img.height, format=img.format, mode=img.mode,
                                 file_bytes=src.stat().st_size, exif=exif, exif_truncated=truncated)

        @tool(mcp, "image_resize")
        def image_resize(input_path: str, output_path: str,
                         width: Annotated[int | None, Field(ge=1, le=MAX_PIXELS)] = None,
                         height: Annotated[int | None, Field(ge=1, le=MAX_PIXELS)] = None,
                         percentage: float | None = None, overwrite: bool = False) -> ResizeResult:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            fmt = _format_for(out)
            with _open(src) as raw:
                img, _ = _upright(raw)
                original = [img.width, img.height]
                new_w, new_h = _target_size(img.width, img.height, width, height, percentage)
                _check_pixels(new_w, new_h)
                img = _for_format(img.resize((new_w, new_h), Image.Resampling.LANCZOS), fmt)
                saved = _save(img, out, fmt)
            return ResizeResult(**saved, original_size=original)

        @tool(mcp, "image_convert")
        def image_convert(input_path: str, output_path: str, format: str, overwrite: bool = False) -> ConvertResult:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            fmt = FORMAT_BY_NAME.get(format.strip().lower())
            if fmt is None:
                raise LatheError("images", "bad_input", f"unsupported format {format!r}.",
                                 "use png, jpeg, webp, avif or bmp.")
            if FORMAT_BY_EXT.get(out.suffix.lower()) != fmt:
                raise LatheError("images", "bad_input", f"output extension {out.suffix!r} does not match {fmt}.",
                                 "name the output with the matching extension, such as .jpg for jpeg.")
            quality = {"JPEG": 85, "WEBP": 85, "AVIF": 80}.get(fmt)
            with _open(src) as raw:
                input_format = raw.format
                img, _ = _upright(raw)
                img = _for_format(img, fmt)
                kwargs = {"quality": quality} if quality else {}
                saved = _save(img, out, fmt, **kwargs)
            return ConvertResult(**saved, input_format=input_format)

        @tool(mcp, "image_optimize")
        def image_optimize(input_path: str, output_path: str, quality: Annotated[int, Field(ge=1, le=100)] = 80,
                           strip_metadata: bool = True, overwrite: bool = False) -> OptimizeResult:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}.get(out.suffix.lower())
            if fmt is None:
                raise LatheError("images", "bad_input", f"optimize writes .jpg, .png or .webp, not {out.suffix!r}.",
                                 "name the output with one of those extensions.")
            original_bytes = src.stat().st_size
            with _open(src) as raw:
                img, rotated = _upright(raw)
                img = _for_format(img, fmt)
                kwargs: dict = {"optimize": True}
                if fmt in ("JPEG", "WEBP"):
                    kwargs["quality"] = quality
                if not strip_metadata:
                    icc = raw.info.get("icc_profile")
                    if icc:
                        kwargs["icc_profile"] = icc
                    exif = raw.getexif()
                    if len(exif):
                        if rotated:
                            exif[ORIENTATION] = 1  # the pixels are already upright
                        kwargs["exif"] = exif.tobytes()
                saved = _save(img, out, fmt, **kwargs)
            new_bytes = saved["output_bytes"]
            savings = round((1 - new_bytes / original_bytes) * 100, 1) if original_bytes else 0.0
            return OptimizeResult(**saved, original_bytes=original_bytes, savings_percent=savings)

        @tool(mcp, "image_crop")
        def image_crop(input_path: str, output_path: str, x: Annotated[int, Field(ge=0)], y: Annotated[int, Field(ge=0)],
                       width: Annotated[int, Field(ge=1)], height: Annotated[int, Field(ge=1)],
                       overwrite: bool = False) -> CropResult:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            fmt = _format_for(out)
            with _open(src) as raw:
                img, _ = _upright(raw)
                if x + width > img.width or y + height > img.height:
                    raise LatheError("images", "bad_input",
                                     f"crop ({x},{y},{width},{height}) is outside the {img.width}x{img.height} image.",
                                     "keep x + width and y + height inside the image size.")
                box = (x, y, x + width, y + height)
                cropped = _for_format(img.crop(box), fmt)
                saved = _save(cropped, out, fmt)
            return CropResult(**saved, crop_box=list(box))

        @tool(mcp, "image_thumbnail")
        def image_thumbnail(input_path: str, output_path: str, size: Annotated[int, Field(ge=1, le=4096)] = 128,
                            overwrite: bool = False) -> ThumbnailResult:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            fmt = _format_for(out)
            with _open(src) as raw:
                img, _ = _upright(raw)
                original = [img.width, img.height]
                img = _for_format(img.copy(), fmt)
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                saved = _save(img, out, fmt)
            return ThumbnailResult(**saved, original_size=original, max_dimension=size)

