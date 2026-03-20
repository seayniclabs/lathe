"""Image processing operations using Pillow.

Handles resize, convert, optimize, crop, thumbnail, and metadata extraction.
All operations are memory-conscious and handle CMYK conversion and EXIF orientation.
"""

from pathlib import Path

from PIL import Image, ExifTags

# Guard against decompression bombs
Image.MAX_IMAGE_PIXELS = 178_956_970  # ~13400x13400


def _fix_orientation(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation tag and remove it from metadata."""
    try:
        exif = img.getexif()
        orientation_key = None
        for key, val in ExifTags.TAGS.items():
            if val == "Orientation":
                orientation_key = key
                break

        if orientation_key is None or orientation_key not in exif:
            return img

        orientation = exif[orientation_key]
        transforms = {
            2: Image.FLIP_LEFT_RIGHT,
            3: Image.ROTATE_180,
            4: Image.FLIP_TOP_BOTTOM,
            5: Image.TRANSPOSE,
            6: Image.ROTATE_270,
            7: Image.TRANSVERSE,
            8: Image.ROTATE_90,
        }
        if orientation in transforms:
            img = img.transpose(transforms[orientation])
    except Exception:
        pass  # EXIF not available or malformed
    return img


def _ensure_rgb(img: Image.Image) -> Image.Image:
    """Convert CMYK or palette images to RGB."""
    if img.mode in ("CMYK", "P", "LA", "PA"):
        return img.convert("RGB")
    if img.mode == "RGBA":
        return img  # Keep alpha for formats that support it
    return img


def resize(
    input_path: Path,
    output_path: Path,
    width: int | None = None,
    height: int | None = None,
    percentage: float | None = None,
) -> dict:
    """Resize an image. Preserves aspect ratio if only one dimension given."""
    img = Image.open(input_path)
    img = _fix_orientation(img)
    orig_w, orig_h = img.size

    if percentage is not None:
        new_w = int(orig_w * percentage / 100)
        new_h = int(orig_h * percentage / 100)
    elif width and height:
        new_w, new_h = width, height
    elif width:
        ratio = width / orig_w
        new_w = width
        new_h = int(orig_h * ratio)
    elif height:
        ratio = height / orig_h
        new_w = int(orig_w * ratio)
        new_h = height
    else:
        raise ValueError("Provide width, height, or percentage")

    img = _ensure_rgb(img)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    resized.save(output_path)

    return {
        "original_size": [orig_w, orig_h],
        "new_size": [new_w, new_h],
        "output_path": str(output_path),
    }


def convert(input_path: Path, output_path: Path, fmt: str) -> dict:
    """Convert image to a different format."""
    img = Image.open(input_path)
    img = _fix_orientation(img)
    img = _ensure_rgb(img)

    save_kwargs = {}
    fmt_upper = fmt.upper()
    if fmt_upper == "JPEG":
        save_kwargs["quality"] = 85
        # JPEG doesn't support alpha
        if img.mode == "RGBA":
            img = img.convert("RGB")
    elif fmt_upper == "WEBP":
        save_kwargs["quality"] = 85
    elif fmt_upper == "AVIF":
        save_kwargs["quality"] = 80

    img.save(output_path, format=fmt_upper, **save_kwargs)

    return {
        "input_format": Image.open(input_path).format,
        "output_format": fmt_upper,
        "output_path": str(output_path),
    }


def optimize(
    input_path: Path,
    output_path: Path,
    quality: int = 80,
    strip_metadata: bool = True,
) -> dict:
    """Optimize image for web delivery."""
    img = Image.open(input_path)
    img = _fix_orientation(img)
    img = _ensure_rgb(img)

    original_size = input_path.stat().st_size

    save_kwargs = {
        "optimize": True,
        "quality": quality,
    }

    # Determine output format from extension
    ext = output_path.suffix.lower()
    fmt_map = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    fmt = fmt_map.get(ext, img.format or "PNG")

    if fmt == "JPEG" and img.mode == "RGBA":
        img = img.convert("RGB")

    if strip_metadata:
        # Create a clean copy without EXIF
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.get_flattened_data()))
        clean.save(output_path, format=fmt, **save_kwargs)
    else:
        img.save(output_path, format=fmt, **save_kwargs)

    new_size = output_path.stat().st_size

    return {
        "original_bytes": original_size,
        "optimized_bytes": new_size,
        "savings_percent": round((1 - new_size / original_size) * 100, 1) if original_size > 0 else 0,
        "output_path": str(output_path),
    }


def get_info(input_path: Path) -> dict:
    """Extract image metadata including EXIF if present."""
    img = Image.open(input_path)
    info = {
        "width": img.width,
        "height": img.height,
        "format": img.format,
        "mode": img.mode,
        "file_size": input_path.stat().st_size,
    }

    # Extract EXIF data
    try:
        exif_data = img.getexif()
        if exif_data:
            exif_readable = {}
            for tag_id, value in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                # Convert bytes to string for JSON serialization
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = str(value)
                exif_readable[tag_name] = str(value)
            info["exif"] = exif_readable
    except Exception:
        info["exif"] = None

    return info


def crop(
    input_path: Path,
    output_path: Path,
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict:
    """Crop a region from the image."""
    img = Image.open(input_path)
    img = _fix_orientation(img)

    # Validate crop bounds
    if x < 0 or y < 0:
        raise ValueError("Crop coordinates must be non-negative")
    if x + width > img.width or y + height > img.height:
        raise ValueError(
            f"Crop region ({x},{y},{width},{height}) exceeds "
            f"image dimensions ({img.width},{img.height})"
        )

    cropped = img.crop((x, y, x + width, y + height))
    cropped.save(output_path)

    return {
        "original_size": [img.width, img.height],
        "crop_region": [x, y, width, height],
        "output_size": [cropped.width, cropped.height],
        "output_path": str(output_path),
    }


def thumbnail(
    input_path: Path,
    output_path: Path,
    size: int = 128,
) -> dict:
    """Generate a thumbnail that fits within size x size."""
    img = Image.open(input_path)
    img = _fix_orientation(img)
    img = _ensure_rgb(img)

    original_size = (img.width, img.height)
    img.thumbnail((size, size), Image.LANCZOS)
    img.save(output_path)

    return {
        "original_size": list(original_size),
        "thumbnail_size": [img.width, img.height],
        "max_dimension": size,
        "output_path": str(output_path),
    }
