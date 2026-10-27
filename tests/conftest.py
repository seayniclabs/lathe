"""Fixtures are generated at test time, so a clean checkout runs with no manual step."""

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

requires_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                     reason="needs ffmpeg and ffprobe")
requires_tesseract = pytest.mark.skipif(not shutil.which("tesseract"), reason="needs tesseract")
requires_ghostscript = pytest.mark.skipif(not shutil.which("gs"), reason="needs ghostscript")


@pytest.fixture
def box(tmp_path: Path) -> Path:
    """The working directory for a test. Every input and output lives here."""
    root = tmp_path / "box"
    root.mkdir()
    return root


def make_png(path: Path, size=(400, 200), color=(200, 30, 30)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def make_text_png(path: Path, text: str = "LATHE 2026") -> Path:
    img = Image.new("L", (900, 220), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=96)
    draw.text((30, 40), text, fill=0, font=font)
    img.save(path)
    return path


def make_pdf(path: Path, pages: int = 2, text: str = "Hello from Lathe") -> Path:
    """A small PDF with a real text layer, written by hand so the test needs no PDF library to create it."""
    objects = []
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(pages))
    objects.append(f"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>")
    font_id = 3 + pages * 2
    for i in range(pages):
        page_id, content_id = 3 + i * 2, 4 + i * 2
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>")
        stream = f"BT /F1 24 Tf 72 720 Td ({text} page {i + 1}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


def make_media(path: Path, kind: str) -> Path:
    """kind: 'wav', 'mp3' (audio), or 'mp4' (video with an audio track). One second long."""
    args = {
        "wav": ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"],
        "mp3": ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"],
        "mp4": ["-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=1",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest"],
    }[kind]
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *args, str(path)], check=True)
    return path
