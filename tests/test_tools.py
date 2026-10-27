"""One call per tool on generated fixtures, plus the path, overwrite and error-shape rules.

Tests that need ffmpeg, tesseract or ghostscript are skipped when the program is missing.
Everything runs inside a temporary working directory.
"""

import asyncio
import re

import pytest
from PIL import Image

import lathe.modules as modules
from conftest import (make_media, make_pdf, make_png, make_text_png, requires_ffmpeg, requires_ghostscript,
                      requires_tesseract)
from lathe.config import Config
from lathe.server import build_server

ERROR = re.compile(r"lathe\.[a-z_]+\.[a-z_]+: ")


def server(box, **env):
    return build_server(Config(env={"LATHE_WORKING_DIR": str(box), **env}, file_data={}))


def call(mcp, name, **args):
    try:
        _, structured = asyncio.run(mcp.call_tool(name, args))
    except Exception as e:  # FastMCP wraps tool errors; the lathe text is inside
        assert ERROR.search(str(e)), f"error does not follow lathe.<module>.<code>: {e}"
        raise
    return structured


def code_of(exc) -> str:
    match = re.search(r"lathe\.[a-z_]+\.([a-z_]+):", str(exc.value))
    assert match, str(exc.value)
    return match.group(1)


# --- images: one call each ---------------------------------------------------

def test_image_info(box):
    make_png(box / "in.png")
    out = call(server(box), "image_info", input_path="in.png")
    assert (out["width"], out["height"], out["format"]) == (400, 200, "PNG")
    assert out["exif_truncated"] is False


def test_image_resize_keeps_aspect_ratio(box):
    make_png(box / "in.png")
    out = call(server(box), "image_resize", input_path="in.png", output_path="out.png", width=100)
    assert out["original_size"] == [400, 200] and (out["width"], out["height"]) == (100, 50)
    assert (box / "out.png").exists()


def test_image_convert(box):
    make_png(box / "in.png")
    out = call(server(box), "image_convert", input_path="in.png", output_path="out.jpg", format="jpeg")
    assert out["format"] == "JPEG" and out["input_format"] == "PNG"
    assert Image.open(box / "out.jpg").format == "JPEG"


def test_image_convert_rejects_mismatched_extension(box):
    make_png(box / "in.png")
    with pytest.raises(Exception) as err:
        call(server(box), "image_convert", input_path="in.png", output_path="out.png", format="jpeg")
    assert code_of(err) == "bad_input"


def test_image_optimize_strips_metadata_by_default(box):
    make_png(box / "in.png")
    out = call(server(box), "image_optimize", input_path="in.png", output_path="out.jpg", quality=60)
    assert out["original_bytes"] > 0 and out["output_bytes"] > 0
    assert len(Image.open(box / "out.jpg").getexif()) == 0


def test_image_crop(box):
    make_png(box / "in.png")
    out = call(server(box), "image_crop", input_path="in.png", output_path="out.png", x=10, y=20, width=50, height=30)
    assert out["crop_box"] == [10, 20, 60, 50] and (out["width"], out["height"]) == (50, 30)


def test_image_crop_outside_image_is_bad_input(box):
    make_png(box / "in.png")
    with pytest.raises(Exception) as err:
        call(server(box), "image_crop", input_path="in.png", output_path="out.png", x=0, y=0, width=999, height=10)
    assert code_of(err) == "bad_input"


def test_image_thumbnail(box):
    make_png(box / "in.png")
    out = call(server(box), "image_thumbnail", input_path="in.png", output_path="t.png", size=64)
    assert max(out["width"], out["height"]) <= 64 and out["original_size"] == [400, 200]


def test_image_unreadable_is_a_lathe_error(box):
    (box / "bad.png").write_bytes(b"not an image at all")
    with pytest.raises(Exception) as err:
        call(server(box), "image_info", input_path="bad.png")
    assert code_of(err) == "unreadable"


# --- paths, overwrite and limits ----------------------------------------------

def test_input_outside_working_dir_is_refused(box, tmp_path):
    outside = make_png(tmp_path / "outside.png")
    with pytest.raises(Exception) as err:
        call(server(box), "image_info", input_path=str(outside))
    assert code_of(err) == "path_denied"


def test_symlink_escape_is_refused(box, tmp_path):
    outside = make_png(tmp_path / "outside.png")
    (box / "link.png").symlink_to(outside)
    with pytest.raises(Exception) as err:
        call(server(box), "image_info", input_path="link.png")
    assert code_of(err) == "path_denied"


def test_output_outside_working_dir_is_refused(box):
    make_png(box / "in.png")
    with pytest.raises(Exception) as err:
        call(server(box), "image_resize", input_path="in.png", output_path="../escape.png", width=10)
    assert code_of(err) == "path_denied"
    assert not (box.parent / "escape.png").exists()


def test_output_never_replaces_input(box):
    make_png(box / "in.png")
    with pytest.raises(Exception) as err:
        call(server(box), "image_resize", input_path="in.png", output_path="in.png", width=10, overwrite=True)
    assert code_of(err) == "same_path"


def test_existing_output_needs_overwrite(box):
    make_png(box / "in.png")
    make_png(box / "out.png", size=(7, 7))
    mcp = server(box)
    with pytest.raises(Exception) as err:
        call(mcp, "image_resize", input_path="in.png", output_path="out.png", width=10)
    assert code_of(err) == "exists"
    assert Image.open(box / "out.png").size == (7, 7)  # untouched
    call(mcp, "image_resize", input_path="in.png", output_path="out.png", width=10, overwrite=True)
    assert Image.open(box / "out.png").size == (10, 5)


def test_missing_input_is_not_found(box):
    with pytest.raises(Exception) as err:
        call(server(box), "image_info", input_path="nope.png")
    assert code_of(err) == "not_found"


def test_file_over_size_limit_is_refused(box):
    (box / "big.png").write_bytes(b"0" * (2 * 1024 * 1024))
    with pytest.raises(Exception) as err:
        call(server(box, LATHE_MAX_FILE_MB="1"), "image_info", input_path="big.png")
    assert code_of(err) == "too_large"


def test_empty_path_is_refused(box):
    with pytest.raises(Exception) as err:
        call(server(box), "image_info", input_path="")
    assert code_of(err) == "bad_path"


# --- pdf ---------------------------------------------------------------------

def test_pdf_info(box):
    make_pdf(box / "doc.pdf", pages=3)
    out = call(server(box), "pdf_info", input_path="doc.pdf")
    assert out["page_count"] == 3 and out["encrypted"] is False


def test_pdf_extract_text_reads_the_text_layer(box):
    make_pdf(box / "doc.pdf", pages=2, text="Hello Lathe")
    out = call(server(box), "pdf_extract_text", input_path="doc.pdf", pages="2")
    assert out["method"] == "text_layer" and out["pages"] == [2]
    assert "Hello Lathe page 2" in out["text"] and out["next_offset"] is None


def test_pdf_extract_text_pages_in_parts(box):
    make_pdf(box / "doc.pdf", pages=2, text="Hello Lathe")
    mcp = server(box)
    first = call(mcp, "pdf_extract_text", input_path="doc.pdf", max_chars=10)
    assert first["returned_chars"] == 10 and first["next_offset"] == 10
    rest = call(mcp, "pdf_extract_text", input_path="doc.pdf", offset=first["next_offset"], max_chars=10_000)
    whole = call(mcp, "pdf_extract_text", input_path="doc.pdf")["text"]
    assert first["text"] + rest["text"] == whole


def test_pdf_bad_page_range(box):
    make_pdf(box / "doc.pdf", pages=2)
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_extract_text", input_path="doc.pdf", pages="9")
    assert code_of(err) == "bad_input"


def test_pdf_merge(box):
    make_pdf(box / "a.pdf", pages=2)
    make_pdf(box / "b.pdf", pages=1)
    out = call(server(box), "pdf_merge", input_paths=["a.pdf", "b.pdf"], output_path="merged.pdf")
    assert out["total_pages"] == 3 and out["input_count"] == 2
    assert call(server(box), "pdf_info", input_path="merged.pdf")["page_count"] == 3


def test_pdf_encrypted_is_reported_not_crashed(box):
    from pypdf import PdfReader, PdfWriter
    make_pdf(box / "plain.pdf", pages=1)
    writer = PdfWriter(clone_from=PdfReader(str(box / "plain.pdf")))
    writer.encrypt("secret-user-password")
    with open(box / "locked.pdf", "wb") as f:
        writer.write(f)
    mcp = server(box)
    info = call(mcp, "pdf_info", input_path="locked.pdf")
    assert info["encrypted"] is True and info["page_count"] is None
    with pytest.raises(Exception) as err:
        call(mcp, "pdf_extract_text", input_path="locked.pdf")
    assert code_of(err) == "encrypted"


@requires_ghostscript
def test_pdf_to_images_renders_pages(box):
    make_pdf(box / "doc.pdf", pages=2)
    out = call(server(box), "pdf_to_images", input_path="doc.pdf", output_dir="pages", dpi=72)
    assert out["count"] == 2
    assert all(p.startswith(str(box / "pages")) for p in out["images"])
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_to_images", input_path="doc.pdf", output_dir="pages", dpi=72)
    assert code_of(err) == "exists"


# --- media -------------------------------------------------------------------

@requires_ffmpeg
def test_audio_info(box):
    make_media(box / "tone.wav", "wav")
    out = call(server(box), "audio_info", input_path="tone.wav")
    assert out["sample_rate"] and out["channels"] == 1 and 0.5 < out["duration_seconds"] < 2


@requires_ffmpeg
def test_audio_convert(box):
    make_media(box / "tone.wav", "wav")
    out = call(server(box), "audio_convert", input_path="tone.wav", output_path="tone.flac", format="flac")
    assert out["format"] == "flac" and out["output_bytes"] > 0


@requires_ffmpeg
def test_audio_convert_rejects_mismatched_extension(box):
    make_media(box / "tone.wav", "wav")
    with pytest.raises(Exception) as err:
        call(server(box), "audio_convert", input_path="tone.wav", output_path="tone.mp3", format="flac")
    assert code_of(err) == "bad_input"


@requires_ffmpeg
def test_video_info(box):
    make_media(box / "clip.mp4", "mp4")
    out = call(server(box), "video_info", input_path="clip.mp4")
    assert (out["width"], out["height"]) == (160, 120) and len(out["audio_tracks"]) == 1


@requires_ffmpeg
def test_video_thumbnail(box):
    make_media(box / "clip.mp4", "mp4")
    out = call(server(box), "video_thumbnail", input_path="clip.mp4", output_path="frame.png", timestamp=0.2)
    assert Image.open(box / "frame.png").size == (160, 120)
    assert out["timestamp_seconds"] == 0.2


def test_media_tool_without_ffprobe_names_the_fix(monkeypatch, box):
    monkeypatch.setattr(modules, "_which", lambda name: None)
    make_png(box / "x.png")
    with pytest.raises(Exception) as err:
        call(server(box), "video_info", input_path="x.png")
    assert code_of(err) == "unavailable" and "Fix: run:" in str(err.value)


# --- ocr ---------------------------------------------------------------------

@requires_tesseract
def test_ocr_image_reads_text(box):
    make_text_png(box / "scan.png", "LATHE 2026")
    out = call(server(box), "ocr_image", input_path="scan.png")
    assert "LATHE" in out["text"].upper() and out["lang"] == "eng"


@requires_tesseract
def test_ocr_rejects_bad_language_code(box):
    make_png(box / "in.png")
    with pytest.raises(Exception) as err:
        call(server(box), "ocr_image", input_path="in.png", lang="eng; rm")
    assert code_of(err) == "bad_input"
