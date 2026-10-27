"""batch_process: dry run, approval for multi-file runs, path safety, and per-file results."""

import os

import pytest
from PIL import Image

from conftest import make_pdf, make_png, requires_ghostscript
from helpers import call, call_with_client, error_code, server

BATCH = {"LATHE_BATCH_ENABLED": "true"}


def photos(box, names=("a.png", "b.png", "c.png")):
    folder = box / "photos"
    folder.mkdir()
    for n in names:
        make_png(folder / n, size=(400, 200))
    return folder


def run_args(**kw):
    args = {"folder": "photos", "operation": "image_resize", "output_folder": "out", "width": 100, "dry_run": False}
    args.update(kw)
    return args


def test_batch_is_off_by_default(box):
    names = {t.name for t in __import__("asyncio").run(server(box).list_tools())}
    assert "batch_process" not in names
    assert "batch_process" in {t.name for t in __import__("asyncio").run(server(box, **BATCH).list_tools())}


def test_dry_run_is_the_default_and_writes_nothing(box):
    photos(box)
    out = call(server(box, **BATCH), "batch_process", folder="photos", operation="image_resize",
               output_folder="out", width=100)
    assert out["dry_run"] is True and out["planned"] == 3 and out["done"] == 0
    assert {i["status"] for i in out["items"]} == {"planned"}
    assert not (box / "out").exists()


def test_multi_file_run_refused_without_a_client(box):
    photos(box)
    with pytest.raises(Exception) as err:
        call(server(box, **BATCH), "batch_process", **run_args())
    assert error_code(err.value) == "approval_unavailable"
    assert not (box / "out").exists()


def test_multi_file_run_after_the_person_approves(box):
    photos(box)
    out, is_error, text, asked = call_with_client(server(box, **BATCH), "batch_process", run_args(), True)
    assert not is_error, text
    assert out["approved_by"] == "person" and out["done"] == 3 and out["failed"] == 0
    assert all(i["status"] == "done" and i["output_bytes"] > 0 for i in out["items"])
    assert sorted(p.name for p in (box / "out").iterdir()) == ["a.png", "b.png", "c.png"]
    assert Image.open(box / "out" / "a.png").width == 100
    assert "Run image_resize on 3 file(s)" in asked[0]


def test_declined_run_writes_nothing(box):
    photos(box)
    _, is_error, text, _ = call_with_client(server(box, **BATCH), "batch_process", run_args(), None)
    assert is_error and error_code(text) == "declined"
    assert not (box / "out").exists()


def test_preapproved_module_runs_without_asking(box):
    photos(box)
    out = call(server(box, **BATCH, LATHE_BATCH_PREAPPROVED="true"), "batch_process", **run_args())
    assert out["approved_by"] == "settings" and out["done"] == 3


def test_single_file_run_does_not_ask(box):
    make_png(box / "one.png")
    out = call(server(box, **BATCH), "batch_process", folder=".", operation="image_resize", output_folder="out",
               pattern="one.png", width=50, dry_run=False)
    assert out["approved_by"] is None and out["done"] == 1
    assert (box / "out" / "one.png").exists()


def test_output_folder_cannot_be_the_input_folder(box):
    photos(box)
    with pytest.raises(Exception) as err:
        call(server(box, **BATCH), "batch_process", **run_args(output_folder="photos"))
    assert error_code(err.value) == "same_path"


def test_existing_outputs_are_skipped_unless_overwrite(box):
    photos(box, names=("a.png",))
    env = {**BATCH, "LATHE_BATCH_PREAPPROVED": "true"}
    call(server(box, **env), "batch_process", **run_args())
    again = call(server(box, **env), "batch_process", **run_args())
    assert again["skipped"] == 1 and again["done"] == 0
    forced = call(server(box, **env), "batch_process", **run_args(overwrite=True))
    assert forced["done"] == 1


def test_max_files_caps_the_plan_and_says_so(box):
    photos(box)
    out = call(server(box, **BATCH), "batch_process", folder="photos", operation="image_thumbnail",
               output_folder="thumbs", max_files=2)
    assert out["matched"] == 3 and out["truncated"] is True and out["planned"] == 2


def test_symlink_outside_the_working_folder_is_rejected(box, tmp_path):
    folder = photos(box, names=("ok.png",))
    outside = tmp_path / "outside.png"
    make_png(outside)
    os.symlink(outside, folder / "link.png")
    out = call(server(box, **BATCH), "batch_process", folder="photos", operation="image_thumbnail",
               output_folder="thumbs")
    statuses = {i["input_path"].rsplit("/", 1)[-1]: i["status"] for i in out["items"]}
    assert statuses == {"link.png": "rejected", "ok.png": "planned"}


def test_two_inputs_that_would_write_the_same_name_are_not_both_run(box):
    folder = box / "mixed"
    folder.mkdir()
    make_png(folder / "shot.png")
    make_png(folder / "shot.jpg")
    out = call(server(box, **BATCH), "batch_process", folder="mixed", operation="image_convert",
               output_folder="out", format="jpeg")
    assert out["planned"] == 1 and out["rejected"] == 1


def test_bad_pattern_is_refused(box):
    photos(box)
    with pytest.raises(Exception) as err:
        call(server(box, **BATCH), "batch_process", folder="photos", operation="image_thumbnail",
             output_folder="out", pattern="../*.png")
    assert error_code(err.value) == "bad_input"


def test_options_are_checked_per_operation(box):
    photos(box)
    with pytest.raises(Exception) as err:
        call(server(box, **BATCH), "batch_process", folder="photos", operation="image_resize", output_folder="out")
    assert error_code(err.value) == "bad_input"


@requires_ghostscript
def test_pdf_to_images_writes_a_folder_per_pdf(box):
    (box / "docs").mkdir()
    make_pdf(box / "docs" / "one.pdf", pages=2)
    out = call(server(box, **BATCH, LATHE_BATCH_PREAPPROVED="true"), "batch_process", folder="docs",
               operation="pdf_to_images", output_folder="pages", dpi=72, dry_run=False)
    assert out["done"] == 1
    assert len(list((box / "pages" / "one").glob("page_*.png"))) == 2


def test_resize_and_convert_do_not_carry_gps_into_the_output(box):
    exif = Image.Exif()
    exif[0x010F] = "Acme Camera"
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (51.0, 30.0, 0.0)
    folder = box / "photos"
    folder.mkdir()
    Image.new("RGB", (400, 200), (90, 90, 200)).save(folder / "trip.jpg", exif=exif)
    out = call(server(box, **BATCH, LATHE_BATCH_PREAPPROVED="true"), "batch_process", folder="photos",
               operation="image_resize", output_folder="web", width=120, dry_run=False)
    assert out["done"] == 1
    assert len(Image.open(box / "web" / "trip.jpg").getexif()) == 0


def test_batch_audio_convert_runs_on_every_clip(box):
    from conftest import make_media, requires_ffmpeg  # noqa: F401  (ffmpeg checked by the skip marker below)
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    folder = box / "clips"
    folder.mkdir()
    make_media(folder / "a.wav", "wav")
    make_media(folder / "b.wav", "wav")
    out = call(server(box, **BATCH, LATHE_BATCH_PREAPPROVED="true"), "batch_process", folder="clips",
               operation="audio_convert", output_folder="mp3", format="mp3", pattern="*.wav", dry_run=False)
    assert out["done"] == 2 and out["failed"] == 0
    assert sorted(p.name for p in (box / "mp3").iterdir()) == ["a.mp3", "b.mp3"]
