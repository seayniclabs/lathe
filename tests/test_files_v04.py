"""0.4 file tools: pdf split and compress, video trim and GIF, and the approval rules they share.

Writing tools ask the person first. A direct call has no client to ask, so it is refused
with approval_unavailable; a client answer, or LATHE_<MODULE>_PREAPPROVED=true, lets it run.
"""

import pytest
from PIL import Image
from pypdf import PdfReader

from conftest import make_media, make_pdf, requires_ffmpeg
from helpers import call, call_with_client, error_code, server


def pdf_pages(path):
    return len(PdfReader(str(path)).pages)


# --- pdf_split ----------------------------------------------------------------

def test_split_refused_when_nobody_can_approve(box):
    make_pdf(box / "doc.pdf", pages=3)
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=2)
    assert error_code(err.value) == "approval_unavailable"
    assert not (box / "parts").exists()


def test_split_runs_after_the_person_approves(box):
    make_pdf(box / "doc.pdf", pages=3)
    out, is_error, text, asked = call_with_client(
        server(box), "pdf_split", {"input_path": "doc.pdf", "output_dir": "parts", "pages_per_file": 2}, True)
    assert not is_error, text
    assert out["approved_by"] == "person" and out["count"] == 2 and out["total_pages"] == 3
    assert [pdf_pages(p) for p in sorted((box / "parts").glob("*.pdf"))] == [2, 1]
    assert "Split doc.pdf (3 pages)" in asked[0]


def test_split_writes_nothing_when_the_person_declines(box):
    make_pdf(box / "doc.pdf", pages=3)
    _, is_error, text, _ = call_with_client(
        server(box), "pdf_split", {"input_path": "doc.pdf", "output_dir": "parts", "pages_per_file": 1}, None)
    assert is_error and error_code(text) == "declined"
    assert not (box / "parts").exists() or not any((box / "parts").iterdir())


def test_split_preapproved_module_runs_without_asking(box):
    make_pdf(box / "doc.pdf", pages=4)
    out = call(server(box, LATHE_PDF_PREAPPROVED="true"), "pdf_split",
               input_path="doc.pdf", output_dir="parts", pages_per_file=2)
    assert out["approved_by"] == "settings" and out["count"] == 2


def test_split_never_overwrites_without_flag(box):
    make_pdf(box / "doc.pdf", pages=2)
    env = {"LATHE_PDF_PREAPPROVED": "true"}
    call(server(box, **env), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=1)
    with pytest.raises(Exception) as err:
        call(server(box, **env), "pdf_split", input_path="doc.pdf", output_dir="parts", pages_per_file=1)
    assert error_code(err.value) == "exists"


# --- pdf_compress -------------------------------------------------------------

def test_compress_keeps_every_page_and_reports_sizes(box):
    make_pdf(box / "doc.pdf", pages=3)
    out = call(server(box, LATHE_PDF_PREAPPROVED="true"), "pdf_compress", input_path="doc.pdf", output_path="small.pdf")
    assert pdf_pages(box / "small.pdf") == 3
    assert out["pages"] == 3 and out["original_bytes"] == (box / "doc.pdf").stat().st_size
    assert out["approved_by"] == "settings"


def test_compress_refused_without_approval(box):
    make_pdf(box / "doc.pdf", pages=1)
    with pytest.raises(Exception) as err:
        call(server(box), "pdf_compress", input_path="doc.pdf", output_path="small.pdf")
    assert error_code(err.value) == "approval_unavailable"
    assert not (box / "small.pdf").exists()


# --- video_trim and video_to_gif ----------------------------------------------

@requires_ffmpeg
def test_video_trim_after_approval(box):
    make_media(box / "clip.mp4", "mp4")
    out, is_error, text, _ = call_with_client(
        server(box), "video_trim", {"input_path": "clip.mp4", "output_path": "cut.mp4", "start": 0.0, "end": 0.5}, True)
    assert not is_error, text
    assert out["approved_by"] == "person" and out["output_bytes"] > 0
    probe = call(server(box), "video_info", input_path="cut.mp4")
    assert 0 < probe["duration_seconds"] <= 1.2


def test_video_trim_rejects_end_before_start(box):
    make_media(box / "clip.mp4", "mp4")
    with pytest.raises(Exception) as err:
        call(server(box, LATHE_MEDIA_PREAPPROVED="true"), "video_trim",
             input_path="clip.mp4", output_path="cut.mp4", start=0.8, end=0.2)
    assert error_code(err.value) == "bad_input"


@requires_ffmpeg
def test_video_to_gif_writes_a_gif(box):
    make_media(box / "clip.mp4", "mp4")
    out = call(server(box, LATHE_MEDIA_PREAPPROVED="true"), "video_to_gif",
               input_path="clip.mp4", output_path="clip.gif", duration=0.5, width=80, fps=5)
    assert out["width"] == 80 and out["fps"] == 5
    assert (box / "clip.gif").read_bytes()[:4] == b"GIF8"
    assert Image.open(box / "clip.gif").format == "GIF"


@requires_ffmpeg
def test_video_to_gif_needs_a_gif_name(box):
    make_media(box / "clip.mp4", "mp4")
    with pytest.raises(Exception) as err:
        call(server(box, LATHE_MEDIA_PREAPPROVED="true"), "video_to_gif", input_path="clip.mp4", output_path="copy.mp4")
    assert error_code(err.value) == "bad_input"
