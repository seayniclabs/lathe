"""scrub_metadata: inspect reads only; scrub writes one new file and never overwrites."""

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from conftest import make_pdf
from helpers import call, error_code, server

PRIVACY = {"LATHE_PRIVACY_ENABLED": "true"}


def photo_with_gps(path):
    exif = Image.Exif()
    exif[0x010F] = "Acme Camera"   # Make
    exif[0x0110] = "Model 9"       # Model
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (51.0, 30.0, 0.0)
    Image.new("RGB", (80, 60), (10, 200, 10)).save(path, exif=exif)
    return path


def pdf_with_author(path):
    make_pdf(path, pages=1)
    writer = PdfWriter(clone_from=PdfReader(str(path)))
    writer.add_metadata({"/Author": "Jane Example", "/Creator": "Word", "/Producer": "Tool", "/Title": "Report"})
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def test_inspect_lists_metadata_and_gps_and_writes_nothing(box):
    photo_with_gps(box / "trip.png")
    out = call(server(box, **PRIVACY), "scrub_metadata", input_path="trip.png")
    names = {f["name"] for f in out["found"]}
    assert {"Make", "Model", "GPSInfo"} <= names
    assert out["gps_present"] is True and out["removed"] == [] and out["output_path"] is None
    assert sorted(p.name for p in box.iterdir()) == ["trip.png"]


def test_scrub_needs_an_output_name(box):
    photo_with_gps(box / "trip.png")
    with pytest.raises(Exception) as err:
        call(server(box, **PRIVACY), "scrub_metadata", input_path="trip.png", mode="scrub")
    assert error_code(err.value) == "bad_input"


def test_scrub_image_writes_one_clean_copy_without_asking(box):
    photo_with_gps(box / "trip.png")
    out = call(server(box, **PRIVACY), "scrub_metadata", input_path="trip.png", mode="scrub", output_path="clean.png")
    assert {"Make", "Model", "GPSInfo"} <= set(out["removed"])
    assert "approved_by" not in out
    clean = Image.open(box / "clean.png")
    assert len(clean.getexif()) == 0 and clean.size == (80, 60)


def test_scrub_never_overwrites_without_flag(box):
    photo_with_gps(box / "trip.png")
    call(server(box, **PRIVACY), "scrub_metadata", input_path="trip.png", mode="scrub", output_path="clean.png")
    with pytest.raises(Exception) as err:
        call(server(box, **PRIVACY), "scrub_metadata", input_path="trip.png", mode="scrub", output_path="clean.png")
    assert error_code(err.value) == "exists"


def test_scrub_pdf_removes_author_creator_producer_and_keeps_title(box):
    pdf_with_author(box / "report.pdf")
    out = call(server(box, **PRIVACY), "scrub_metadata", input_path="report.pdf", mode="scrub", output_path="clean.pdf")
    assert set(out["removed"]) >= {"Author", "Creator", "Producer"}
    assert "Title" in out["kept"]
    meta = dict(PdfReader(str(box / "clean.pdf")).metadata or {})
    assert "/Author" not in meta and "/Creator" not in meta and "/Producer" not in meta
    assert meta.get("/Title") == "Report"


def test_scrub_jpeg_removes_gps_and_keeps_pixels_upright(box):
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90 degrees clockwise to display
    exif[0x010F] = "Acme Camera"
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (33.0, 52.0, 0.0)
    Image.new("RGB", (80, 40), (200, 10, 10)).save(box / "phone.jpg", exif=exif)
    out = call(server(box, **PRIVACY), "scrub_metadata", input_path="phone.jpg", mode="scrub", output_path="clean.jpg")
    assert {"GPSInfo", "Make", "Orientation"} <= set(out["removed"])
    clean = Image.open(box / "clean.jpg")
    assert len(clean.getexif()) == 0
    assert clean.size == (40, 80)  # the rotation was applied to the pixels before the tag was removed
