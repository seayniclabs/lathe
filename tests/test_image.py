"""Tests for Lathe image processing tools.

Run `python tests/generate_fixtures.py` first to create fixture files.
"""

import os
from pathlib import Path

import pytest
from PIL import Image

from lathe.image_ops import convert, crop, get_info, optimize, resize, thumbnail

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def require_fixtures():
    """Skip all tests if fixtures haven't been generated."""
    if not (FIXTURES / "image_rgb.png").exists():
        pytest.skip("Fixtures not generated. Run: python tests/generate_fixtures.py")


class TestImageInfo:
    def test_returns_correct_dimensions(self):
        info = get_info(FIXTURES / "image_rgb.png")
        assert info["width"] == 800
        assert info["height"] == 600

    def test_returns_format(self):
        info = get_info(FIXTURES / "image_rgb.png")
        assert info["format"] == "PNG"

    def test_returns_mode(self):
        info = get_info(FIXTURES / "image_rgb.png")
        assert info["mode"] == "RGB"

    def test_returns_file_size(self):
        info = get_info(FIXTURES / "image_rgb.png")
        assert info["file_size"] > 0

    def test_jpeg_info(self):
        info = get_info(FIXTURES / "image_exif.jpg")
        assert info["width"] == 640
        assert info["height"] == 480
        assert info["format"] == "JPEG"


class TestImageResize:
    def test_resize_by_width(self, tmp_path):
        out = tmp_path / "resized.png"
        result = resize(FIXTURES / "image_rgb.png", out, width=400)
        assert result["new_size"][0] == 400
        # Aspect ratio preserved: 800:600 = 400:300
        assert result["new_size"][1] == 300
        assert out.exists()

    def test_resize_by_height(self, tmp_path):
        out = tmp_path / "resized.png"
        result = resize(FIXTURES / "image_rgb.png", out, height=300)
        assert result["new_size"][1] == 300
        assert result["new_size"][0] == 400

    def test_resize_by_percentage(self, tmp_path):
        out = tmp_path / "resized.png"
        result = resize(FIXTURES / "image_rgb.png", out, percentage=50)
        assert result["new_size"] == [400, 300]

    def test_resize_explicit_dimensions(self, tmp_path):
        out = tmp_path / "resized.png"
        result = resize(FIXTURES / "image_rgb.png", out, width=200, height=100)
        assert result["new_size"] == [200, 100]

    def test_resize_no_params_raises(self, tmp_path):
        out = tmp_path / "resized.png"
        with pytest.raises(ValueError, match="Provide width"):
            resize(FIXTURES / "image_rgb.png", out)


class TestImageConvert:
    def test_png_to_jpeg(self, tmp_path):
        out = tmp_path / "converted.jpg"
        result = convert(FIXTURES / "image_rgb.png", out, "jpeg")
        assert result["output_format"] == "JPEG"
        assert out.exists()
        # Verify it's actually JPEG
        img = Image.open(out)
        assert img.format == "JPEG"

    def test_png_to_webp(self, tmp_path):
        out = tmp_path / "converted.webp"
        result = convert(FIXTURES / "image_rgb.png", out, "webp")
        assert result["output_format"] == "WEBP"
        assert out.exists()

    def test_jpeg_to_png(self, tmp_path):
        out = tmp_path / "converted.png"
        result = convert(FIXTURES / "image_exif.jpg", out, "png")
        assert result["output_format"] == "PNG"


class TestImageOptimize:
    def test_produces_smaller_file(self, tmp_path):
        # Create a large uncompressed BMP to ensure optimization shrinks it
        from PIL import Image as PILImage
        big_png = tmp_path / "big.png"
        img = PILImage.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(big_png, format="PNG", compress_level=0)
        out = tmp_path / "optimized.jpg"
        result = optimize(big_png, out, quality=60)
        assert result["optimized_bytes"] < result["original_bytes"]

    def test_strip_metadata(self, tmp_path):
        out = tmp_path / "stripped.jpg"
        result = optimize(FIXTURES / "image_exif.jpg", out, strip_metadata=True)
        assert out.exists()

    def test_quality_parameter(self, tmp_path):
        out_low = tmp_path / "low.jpg"
        out_high = tmp_path / "high.jpg"
        optimize(FIXTURES / "image_rgb.png", out_low, quality=20)
        optimize(FIXTURES / "image_rgb.png", out_high, quality=95)
        # Lower quality should produce smaller file
        assert out_low.stat().st_size < out_high.stat().st_size


class TestImageCrop:
    def test_crop_produces_correct_dimensions(self, tmp_path):
        out = tmp_path / "cropped.png"
        result = crop(FIXTURES / "image_rgb.png", out, x=0, y=0, width=200, height=100)
        assert result["output_size"] == [200, 100]
        img = Image.open(out)
        assert img.size == (200, 100)

    def test_crop_center_region(self, tmp_path):
        out = tmp_path / "cropped.png"
        result = crop(FIXTURES / "image_rgb.png", out, x=100, y=100, width=300, height=200)
        assert result["output_size"] == [300, 200]

    def test_crop_out_of_bounds_raises(self, tmp_path):
        out = tmp_path / "cropped.png"
        with pytest.raises(ValueError, match="exceeds image dimensions"):
            crop(FIXTURES / "image_rgb.png", out, x=700, y=500, width=200, height=200)

    def test_crop_negative_coordinates_raises(self, tmp_path):
        out = tmp_path / "cropped.png"
        with pytest.raises(ValueError, match="non-negative"):
            crop(FIXTURES / "image_rgb.png", out, x=-10, y=0, width=100, height=100)


class TestImageThumbnail:
    def test_fits_within_size(self, tmp_path):
        out = tmp_path / "thumb.png"
        result = thumbnail(FIXTURES / "image_rgb.png", out, size=128)
        img = Image.open(out)
        assert img.width <= 128
        assert img.height <= 128

    def test_preserves_aspect_ratio(self, tmp_path):
        out = tmp_path / "thumb.png"
        result = thumbnail(FIXTURES / "image_rgb.png", out, size=128)
        # Original is 800x600 (4:3), thumbnail should maintain ratio
        img = Image.open(out)
        ratio = img.width / img.height
        assert abs(ratio - 800 / 600) < 0.02

    def test_custom_size(self, tmp_path):
        out = tmp_path / "thumb.png"
        result = thumbnail(FIXTURES / "image_rgb.png", out, size=64)
        img = Image.open(out)
        assert img.width <= 64
        assert img.height <= 64
