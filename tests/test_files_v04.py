"""0.4 single-file writers: pdf split and compress, video trim and GIF.

Each call writes one new file (or one folder of parts) without asking. It never overwrites
an existing output unless overwrite=true, and it refuses a symbolic link as the output folder.
Only batch_process asks for approval (see test_batch.py).
"""

import pytest
from pypdf import PdfReader
from PIL import Image

from conftest import make_media, make_pdf, requires_ffmpeg
from helpers import call, error_code, server

MEDIA = {"LATHE_MEDIA_ENABLED": "true"}


def pdf_pages(path):
    return len(PdfReader(str(path)).pages)


# --- pdf_split ----------------------------------------------------------------

def test_split_writes_parts_without_asking(box):
    make_pdf(box / "doc.pdf", pages=3)
    out = call(server(box), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=2)
    assert out["count"] == 2 and out["total_pages"] == 3
    assert [pdf_pages(p) for p in sorted((box / "parts").glob("*.pdf"))] == [2, 1]


def test_split_never_overwrites_without_flag(box):
    make_pdf(box / "doc.pdf", pages=2)
    call(server(box), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=1)
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=1)
    assert error_code(err.value) == "exists"
    again = call(server(box), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=1, overwrite=True)
    assert again["count"] == 2


def test_split_refuses_a_symlinked_output_folder(box, tmp_path):
    make_pdf(box / "doc.pdf", pages=2)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (box / "parts").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_split", input_path="doc.pdf", output_dir="parts")
    assert error_code(err.value) == "path_denied"
    assert list(elsewhere.iterdir()) == []


# --- pdf_compress -------------------------------------------------------------

def test_compress_writes_one_copy_with_every_page(box):
    make_pdf(box / "doc.pdf", pages=3)
    out = call(server(box), "pdf_compress", input_path="doc.pdf", output_path="small.pdf")
    assert pdf_pages(box / "small.pdf") == 3
    assert out["pages"] == 3 and out["original_bytes"] == (box / "doc.pdf").stat().st_size
    assert "approved_by" not in out


def test_compress_never_overwrites_without_flag(box):
    make_pdf(box / "doc.pdf", pages=1)
    call(server(box), "pdf_compress", input_path="doc.pdf", output_path="small.pdf")
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_compress", input_path="doc.pdf", output_path="small.pdf")
    assert error_code(err.value) == "exists"


# --- video_trim and video_to_gif ----------------------------------------------

@requires_ffmpeg
def test_video_trim_writes_a_clip(box):
    make_media(box / "clip.mp4", "mp4")
    out = call(server(box, **MEDIA), "video_trim", input_path="clip.mp4", output_path="cut.mp4", start=0.0, end=0.5)
    assert out["output_bytes"] > 0 and "approved_by" not in out
    probe = call(server(box), "video_info", input_path="cut.mp4")
    assert 0 < probe["duration_seconds"] <= 1.2


@requires_ffmpeg
def test_video_trim_rejects_end_before_start(box):
    make_media(box / "clip.mp4", "mp4")
    with pytest.raises(Exception) as err:
        call(server(box, **MEDIA), "video_trim", input_path="clip.mp4", output_path="cut.mp4", start=0.8, end=0.2)
    assert error_code(err.value) == "bad_input"


@requires_ffmpeg
def test_video_to_gif_writes_a_gif(box):
    make_media(box / "clip.mp4", "mp4")
    out = call(server(box, **MEDIA), "video_to_gif",
               input_path="clip.mp4", output_path="clip.gif", duration=0.5, width=80, fps=5)
    assert out["width"] == 80 and out["fps"] == 5
    assert (box / "clip.gif").read_bytes()[:4] == b"GIF8"
    assert Image.open(box / "clip.gif").format == "GIF"


@requires_ffmpeg
def test_video_to_gif_needs_a_gif_name(box):
    make_media(box / "clip.mp4", "mp4")
    with pytest.raises(Exception) as err:
        call(server(box, **MEDIA), "video_to_gif", input_path="clip.mp4", output_path="copy.mp4")
    assert error_code(err.value) == "bad_input"
