"""Lathe MCP server — file and media processing tools.

Exposes image, PDF, audio, and video processing operations as MCP tools.
Uses FastMCP for tool registration and transport.

Free tier: 6 image tools + health + upgrade_info
Licensed tier: All 16 tools (images + PDF + audio/video + OCR)
"""

import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .license import is_licensed
from .security import (
    PathSecurityError,
    check_dependency,
    check_file_size,
    get_dependency_status,
    validate_input_path,
    validate_output_path,
)
from . import image_ops, pdf_ops, media_ops

mcp = FastMCP(
    "Lathe",
    instructions="File and media processing MCP server — resize, convert, optimize, extract.",
)

# Working directory: default to cwd, can be overridden via LATHE_WORKING_DIR
WORKING_DIR = os.environ.get("LATHE_WORKING_DIR", os.getcwd())

# License state — evaluated once at server startup
_licensed = is_licensed()

# Count available tools for health reporting
_FREE_TOOL_COUNT = 7  # 6 image + health
_LICENSED_TOOL_COUNT = 16  # all tools


def _input(path: str) -> Path:
    """Validate and resolve an input path."""
    resolved = validate_input_path(path, WORKING_DIR)
    check_file_size(resolved)
    return resolved


def _output(path: str) -> Path:
    """Validate and resolve an output path."""
    return validate_output_path(path, WORKING_DIR)


# --- Health ---

@mcp.tool()
def health() -> dict:
    """Check server status, version, and available external dependencies."""
    deps = get_dependency_status()
    tool_count = _LICENSED_TOOL_COUNT if _licensed else _FREE_TOOL_COUNT + 1  # +1 for upgrade_info
    return {
        "status": "ok",
        "version": __version__,
        "tier": "licensed" if _licensed else "free",
        "tools_available": tool_count,
        "working_dir": WORKING_DIR,
        "dependencies": deps,
    }


# --- Image Tools (always available) ---

@mcp.tool()
def image_info(input_path: str) -> dict:
    """Get image metadata: dimensions, format, mode, file size, EXIF data.

    Args:
        input_path: Path to the image file.
    """
    path = _input(input_path)
    return image_ops.get_info(path)


@mcp.tool()
def image_resize(
    input_path: str,
    output_path: str,
    width: int | None = None,
    height: int | None = None,
    percentage: float | None = None,
) -> dict:
    """Resize an image. Preserves aspect ratio if only one dimension given.

    Args:
        input_path: Path to the source image.
        output_path: Path for the resized image.
        width: Target width in pixels.
        height: Target height in pixels.
        percentage: Scale by percentage (e.g. 50 = half size).
    """
    inp = _input(input_path)
    out = _output(output_path)
    return image_ops.resize(inp, out, width=width, height=height, percentage=percentage)


@mcp.tool()
def image_convert(input_path: str, output_path: str, format: str) -> dict:
    """Convert image to a different format (png, jpeg, webp, avif, bmp).

    Args:
        input_path: Path to the source image.
        output_path: Path for the converted image.
        format: Target format: png, jpeg, webp, avif, bmp.
    """
    inp = _input(input_path)
    out = _output(output_path)
    return image_ops.convert(inp, out, format)


@mcp.tool()
def image_optimize(
    input_path: str,
    output_path: str,
    quality: int = 80,
    strip_metadata: bool = True,
) -> dict:
    """Optimize image for web delivery. Reduces file size while preserving quality.

    Args:
        input_path: Path to the source image.
        output_path: Path for the optimized image.
        quality: Quality level 1-100 (default 80).
        strip_metadata: Remove EXIF and other metadata (default true).
    """
    inp = _input(input_path)
    out = _output(output_path)
    return image_ops.optimize(inp, out, quality=quality, strip_metadata=strip_metadata)


@mcp.tool()
def image_crop(
    input_path: str,
    output_path: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict:
    """Crop a rectangular region from an image.

    Args:
        input_path: Path to the source image.
        output_path: Path for the cropped image.
        x: Left edge of crop region (pixels from left).
        y: Top edge of crop region (pixels from top).
        width: Width of crop region.
        height: Height of crop region.
    """
    inp = _input(input_path)
    out = _output(output_path)
    return image_ops.crop(inp, out, x=x, y=y, width=width, height=height)


@mcp.tool()
def image_thumbnail(
    input_path: str,
    output_path: str,
    size: int = 128,
) -> dict:
    """Generate a thumbnail that fits within a square of the given size.

    Args:
        input_path: Path to the source image.
        output_path: Path for the thumbnail.
        size: Maximum dimension in pixels (default 128).
    """
    inp = _input(input_path)
    out = _output(output_path)
    return image_ops.thumbnail(inp, out, size=size)


# --- Licensed Tools (PDF, Audio, Video, OCR) ---

if _licensed:
    # --- PDF Tools ---

    @mcp.tool()
    def pdf_info(input_path: str) -> dict:
        """Get PDF metadata: page count, file size, title, author, encrypted status.

        Args:
            input_path: Path to the PDF file.
        """
        path = _input(input_path)
        return pdf_ops.get_info(path)

    @mcp.tool()
    def pdf_extract_text(input_path: str, pages: str | None = None) -> dict:
        """Extract text from PDF. Falls back to OCR if no text layer found.

        Args:
            input_path: Path to the PDF file.
            pages: Optional page range like "1-3" or "2" (1-indexed).
        """
        path = _input(input_path)
        return pdf_ops.extract_text(path, pages=pages)

    @mcp.tool()
    def pdf_merge(input_paths: list[str], output_path: str) -> dict:
        """Merge multiple PDF files into one.

        Args:
            input_paths: List of paths to PDF files to merge, in order.
            output_path: Path for the merged PDF.
        """
        inputs = [_input(p) for p in input_paths]
        out = _output(output_path)
        return pdf_ops.merge(inputs, out)

    @mcp.tool()
    def pdf_to_images(
        input_path: str,
        output_dir: str,
        pages: str | None = None,
        format: str = "png",
    ) -> dict:
        """Convert PDF pages to images. Requires ghostscript.

        Args:
            input_path: Path to the PDF file.
            output_dir: Directory for output images.
            pages: Optional page range like "1-3" (1-indexed).
            format: Output format: png or jpeg (default png).
        """
        inp = _input(input_path)
        out = _output(os.path.join(output_dir, ".placeholder"))
        out_dir = out.parent
        return pdf_ops.to_images(inp, out_dir, pages=pages, fmt=format)

    # --- Audio Tools ---

    @mcp.tool()
    def audio_convert(input_path: str, output_path: str, format: str) -> dict:
        """Convert audio to a different format. Requires ffmpeg.

        Args:
            input_path: Path to the source audio file.
            output_path: Path for the converted audio.
            format: Target format: mp3, wav, flac, aac, ogg.
        """
        inp = _input(input_path)
        out = _output(output_path)
        return media_ops.audio_convert(inp, out, format)

    @mcp.tool()
    def audio_info(input_path: str) -> dict:
        """Get audio metadata: duration, format, bitrate, sample rate, channels. Requires ffmpeg.

        Args:
            input_path: Path to the audio file.
        """
        path = _input(input_path)
        return media_ops.audio_info(path)

    # --- Video Tools ---

    @mcp.tool()
    def video_thumbnail(
        input_path: str,
        output_path: str,
        timestamp: float = 0,
    ) -> dict:
        """Extract a single frame from a video as an image. Requires ffmpeg.

        Args:
            input_path: Path to the video file.
            output_path: Path for the extracted frame image.
            timestamp: Time in seconds to extract frame from (default 0).
        """
        inp = _input(input_path)
        out = _output(output_path)
        return media_ops.video_thumbnail(inp, out, timestamp=timestamp)

    @mcp.tool()
    def video_info(input_path: str) -> dict:
        """Get video metadata: duration, resolution, codec, bitrate, audio tracks. Requires ffmpeg.

        Args:
            input_path: Path to the video file.
        """
        path = _input(input_path)
        return media_ops.video_info(path)

    # --- OCR Tool ---

    @mcp.tool()
    def ocr_image(input_path: str) -> dict:
        """Extract text from an image using OCR. Requires tesseract.

        Args:
            input_path: Path to the image file.
        """
        if not check_dependency("tesseract"):
            raise RuntimeError(
                "tesseract is required for OCR. "
                "Install with: brew install tesseract (macOS) / apt install tesseract-ocr (Debian)"
            )

        path = _input(input_path)

        result = subprocess.run(
            ["tesseract", str(path), "stdout"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Tesseract failed: {result.stderr}")

        text = result.stdout.strip()
        return {
            "text": text,
            "char_count": len(text),
            "input_path": str(path),
        }

else:
    # --- Free tier: show upgrade info instead of paid tools ---

    @mcp.tool()
    def upgrade_info() -> dict:
        """Information about the full licensed version of Lathe.

        The free version includes 6 image processing tools. The full version
        adds PDF operations, audio/video processing, and OCR — 16 tools total.
        """
        return {
            "current_tier": "free",
            "free_tools": [
                "image_info", "image_resize", "image_convert",
                "image_optimize", "image_crop", "image_thumbnail",
                "health",
            ],
            "paid_tools": [
                "pdf_info", "pdf_extract_text", "pdf_merge", "pdf_to_images",
                "audio_convert", "audio_info",
                "video_thumbnail", "video_info",
                "ocr_image",
            ],
            "price": "$19 — one-time purchase",
            "purchase_url": "https://seayniclabs.com",
            "activation": (
                "Set the LATHE_LICENSE_KEY environment variable, or place your "
                "license file at ~/.seayniclabs/license.json"
            ),
        }


def _log_startup_dependencies() -> None:
    """Print optional dependency availability to stderr on server start."""
    import sys

    for name, info in get_dependency_status().items():
        if info["available"]:
            print(f"[Lathe] {name}: available", file=sys.stderr)
        else:
            print(
                f"[Lathe] {name}: not found — install with: {info['install_hint']}",
                file=sys.stderr,
            )


def main():
    """Run the Lathe MCP server."""
    _log_startup_dependencies()
    mcp.run()


if __name__ == "__main__":
    main()
