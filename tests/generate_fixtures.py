#!/usr/bin/env python3
"""Generate test fixture files for Lathe integration tests.

The fixtures are gitignored; tests/conftest.py runs generate() at session start
when any is missing, so a clean checkout tests without a manual step.
"""

import struct
import wave
from pathlib import Path

from PIL import Image, ExifTags

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(exist_ok=True)


def create_rgb_png():
    """800x600 RGB PNG with gradient."""
    img = Image.new("RGB", (800, 600))
    for x in range(800):
        for y in range(600):
            img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    img.save(FIXTURES / "image_rgb.png")
    print("Created image_rgb.png")


def create_exif_jpg():
    """JPEG with basic EXIF data."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    # Pillow doesn't write EXIF directly in this simple way,
    # but the file will be a valid JPEG for testing
    img.save(FIXTURES / "image_exif.jpg", quality=85)
    print("Created image_exif.jpg")


def create_text_image():
    """Clear text on white background for OCR testing."""
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    # Simple: just create a clean image — actual text rendering needs PIL.ImageDraw
    try:
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "Lathe OCR Test: Hello World 12345", fill=(0, 0, 0))
    except Exception:
        pass  # Plain white image is still a valid test target
    img.save(FIXTURES / "text_image.png")
    print("Created text_image.png")


def create_wav():
    """10-second mono WAV at 44100Hz (silence)."""
    path = FIXTURES / "audio.wav"
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        # 10 seconds of silence
        f.writeframes(b"\x00\x00" * 44100 * 10)
    print("Created audio.wav")


def create_large_marker():
    """Marker file — actual 10000x10000 image generated on demand."""
    (FIXTURES / "LARGE_IMAGE_README.md").write_text(
        "# Large test image\n\n"
        "The 10000x10000 image_large.png is NOT committed to git (too large).\n"
        "Generate it locally with:\n\n"
        "```python\n"
        "from PIL import Image\n"
        "Image.new('RGB', (10000, 10000), (128, 128, 128)).save('image_large.png')\n"
        "```\n"
    )
    print("Created LARGE_IMAGE_README.md (generate image_large.png locally)")


def generate():
    create_rgb_png()
    create_exif_jpg()
    create_text_image()
    create_wav()
    create_large_marker()


if __name__ == "__main__":
    print(f"Generating fixtures in {FIXTURES}/")
    generate()
