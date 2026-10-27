"""Trust surface: approval log, --doctor, skills as prompts, publisher fields, and the locks."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import make_pdf, make_png
from helpers import call, call_with_client, server
from lathe.config import Config
from lathe.server import INSTRUCTIONS, build_server

ROOT = Path(__file__).resolve().parent.parent


def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


BATCH = {"LATHE_BATCH_ENABLED": "true"}


def two_pngs(box):
    folder = box / "pics"
    folder.mkdir()
    for n in ("a.png", "b.png"):
        make_png(folder / n)


def batch_args(**kw):
    args = {"folder": "pics", "operation": "image_thumbnail", "output_folder": "thumbs", "dry_run": False}
    args.update(kw)
    return args


def test_approval_log_records_request_and_grant_without_contents(box, tmp_path):
    log = tmp_path / "approvals.jsonl"
    two_pngs(box)
    call_with_client(server(box, LATHE_APPROVAL_LOG=str(log), **BATCH), "batch_process", batch_args(), True)
    rows = read_log(log)
    assert [r["decision"] for r in rows] == ["requested", "approved"]
    assert rows[1]["approved_by"] == "person" and rows[1]["files"] == 2
    # Only operation, folders, pattern and counts: never file contents, and no file names.
    assert set(rows[0]) == {"ts", "tool", "decision", "approved_by", "operation", "folder", "output_folder", "pattern", "files"}
    assert "PNG" not in log.read_text() and "a.png" not in log.read_text()


def test_approval_log_records_refusal(box, tmp_path):
    log = tmp_path / "approvals.jsonl"
    two_pngs(box)
    with pytest.raises(Exception):
        call(server(box, LATHE_APPROVAL_LOG=str(log), **BATCH), "batch_process", **batch_args())
    assert [r["decision"] for r in read_log(log)] == ["refused"]


def test_approval_log_records_decline(box, tmp_path):
    log = tmp_path / "approvals.jsonl"
    two_pngs(box)
    call_with_client(server(box, LATHE_APPROVAL_LOG=str(log), **BATCH), "batch_process", batch_args(), None)
    assert [r["decision"] for r in read_log(log)] == ["requested", "declined"]


def test_single_file_writes_are_not_logged_as_approvals(box, tmp_path):
    log = tmp_path / "approvals.jsonl"
    make_pdf(box / "doc.pdf", pages=2)
    call(server(box, LATHE_APPROVAL_LOG=str(log)), "pdf_compress", input_path="doc.pdf", output_path="small.pdf")
    assert read_log(log) == []


def test_doctor_exits_1_and_names_fixes_when_pieces_are_missing(tmp_path):
    empty_path = tmp_path / "no-programs"
    empty_path.mkdir()
    env = {"PATH": str(empty_path), "HOME": str(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "lathe.server", "--doctor"], env=env, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 1
    assert "FIX" in r.stdout and "ffmpeg" in r.stdout
    assert "brew install ffmpeg" in r.stdout or "apt install ffmpeg" in r.stdout
    assert "approval log" in r.stdout


def test_discovery_names_publisher_homepage_and_skills(box):
    out = call(server(box), "lathe_modules")
    assert out["publisher"] == "Seaynic Labs"
    assert out["homepage"] == "https://github.com/seayniclabs/lathe"
    assert {s["name"] for s in out["skills"]} >= {"getting-started", "pdf", "pdf-forms", "web-image-prep"}
    assert all(s["license"] == "MIT" for s in out["skills"])


def test_each_skill_is_served_as_a_prompt_and_resource(box):
    mcp = server(box, LATHE_BATCH_ENABLED="true", LATHE_PRIVACY_ENABLED="true")
    prompts = {p.name for p in asyncio.run(mcp.list_prompts())}
    skill_dirs = {p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()}
    assert prompts == skill_dirs
    resources = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    for name in skill_dirs:
        assert f"skill://lathe/{name}/SKILL.md" in resources


def test_skills_carry_license_source_and_author_in_frontmatter():
    for path in (ROOT / "skills").glob("*/SKILL.md"):
        text = path.read_text()
        for key in ("name:", "description:", "license: MIT", "source: https://github.com/seayniclabs/lathe", "author: Seaynic Labs"):
            assert key in text, f"{path.parent.name} is missing {key!r}"


def test_no_promotion_reaches_the_model():
    mcp = build_server(Config(env={"LATHE_BATCH_ENABLED": "true", "LATHE_PRIVACY_ENABLED": "true"}, file_data={}))
    texts = [INSTRUCTIONS]
    texts += [t.description for t in asyncio.run(mcp.list_tools())]
    for p in asyncio.run(mcp.list_prompts()):
        texts.append(asyncio.run(mcp.get_prompt(p.name)).messages[0].content.text)
    for text in texts:
        assert "seayniclabs.com" not in text.lower()


def test_tool_lock_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "tool_lock.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_security_card_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "security_card.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_skill_checker_passes():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_skills.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
