"""Start-and-list, discovery, module switches, missing pieces, config, and the real transports.

Nothing here touches the network or needs external programs. Every test starts from an empty environment.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from lathe import __version__
from lathe.config import Config
import lathe.modules as modules
from lathe.server import build_server

ALL = {
    "health", "lathe_modules",
    "image_info", "image_resize", "image_convert", "image_optimize", "image_crop", "image_thumbnail",
    "pdf_info", "pdf_extract_text", "pdf_merge", "pdf_to_images", "pdf_split", "pdf_compress",
    "audio_info", "audio_convert", "video_info", "video_thumbnail", "video_trim", "video_to_gif",
    "ocr_image",
}


def server(env=None, **kw):
    return build_server(Config(env=env or {}, file_data={}), **kw)


def tool_names(mcp):
    return {t.name for t in asyncio.run(mcp.list_tools())}


def call(mcp, name, **args):
    _, structured = asyncio.run(mcp.call_tool(name, args))
    return structured


def test_empty_env_starts_and_lists_every_tool():
    assert tool_names(server({})) == ALL


def test_every_tool_has_an_output_schema():
    assert all(t.outputSchema for t in asyncio.run(server({}).list_tools()))


def test_module_switch_off_hides_its_tools():
    names = tool_names(server({"LATHE_PDF_ENABLED": "false"}))
    assert not any(n.startswith("pdf_") for n in names)
    assert "image_info" in names


def test_config_file_is_read_and_env_wins(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[core]\nworking_dir = "/from/file"\n\n[ocr]\nlang = "fra"\n\n[media]\nenabled = false\n')
    env = {"LATHE_CONFIG": str(cfg_file), "LATHE_OCR_LANG": "eng"}
    cfg = Config(env=env)
    assert cfg.get("ocr", "lang") == "eng"
    assert cfg.get("core", "working_dir") == "/from/file"
    assert cfg.enabled("media", True) is False


def test_malformed_config_file_does_not_crash(tmp_path):
    bad = tmp_path / "config.toml"
    bad.write_text("this is = not [valid toml")
    mcp = build_server(Config(env={"LATHE_CONFIG": str(bad)}))
    out = call(mcp, "lathe_modules")
    assert "ignored" in out["config_error"]
    assert len(tool_names(mcp)) == len(ALL)


def test_discovery_reports_missing_pieces_with_install_command(monkeypatch):
    monkeypatch.setattr(modules, "_which", lambda name: None)
    monkeypatch.setattr(modules, "_has_python_module", lambda name: False)
    out = call(server({}), "lathe_modules", module="pdf")
    pdf = out["modules"][0]
    assert pdf["available"] is False
    assert {m["name"] for m in pdf["missing"]} == {"pypdf", "gs"}
    assert any(m["install"] == 'pip install "lathe-mcp[pdf]"' for m in pdf["missing"])
    tool = {t["name"]: t for t in pdf["tools"]}["pdf_to_images"]
    assert tool["available"] is False


def test_unavailable_tool_names_the_fix_and_still_starts(monkeypatch, box):
    monkeypatch.setattr(modules, "_which", lambda name: None)
    mcp = server({"LATHE_WORKING_DIR": str(box)})
    assert "ocr_image" in tool_names(mcp)
    with pytest.raises(Exception) as err:
        call(mcp, "ocr_image", input_path="x.png")
    assert "lathe.ocr.unavailable" in str(err.value) and "Fix: run:" in str(err.value)


def test_images_module_is_always_available():
    out = call(server({}), "lathe_modules", module="images")
    assert out["modules"][0]["available"] is True and out["modules"][0]["missing"] == []


def test_discovery_detail_lists_settings_without_values():
    out = call(server({"LATHE_OCR_LANG": "secret-looking-value"}), "lathe_modules", module="ocr")
    settings = {s["env_var"]: s for s in out["modules"][0]["settings"]}
    assert settings["LATHE_OCR_LANG"]["set"] is True
    assert "secret-looking-value" not in json.dumps(out)


def test_health_lists_dependencies():
    out = call(server({}), "health")
    assert out["status"] == "ok" and out["version"] == __version__
    assert {d["name"] for d in out["dependencies"]} >= {"pypdf", "pytesseract", "ffmpeg", "tesseract", "gs"}


def test_stdio_process_starts_with_empty_env(tmp_path):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "lathe.server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, text=True, cwd=tmp_path)
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    replies = _exchange(proc, msgs)
    assert replies[1]["result"]["serverInfo"] == {"name": "lathe", "version": __version__}
    assert {t["name"] for t in replies[2]["result"]["tools"]} == ALL


def test_streamable_http_answers_initialize(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "lathe.server", "--transport", "http", "--port", str(port)],
                            env=env, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        reply = None
        for _ in range(100):
            try:
                reply = httpx.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=headers, timeout=2)
                break
            except httpx.HTTPError:
                time.sleep(0.2)
        assert reply is not None and reply.status_code == 200
        assert '"name":"lathe"' in reply.text.replace(" ", "") and __version__ in reply.text
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _exchange(proc, msgs, timeout=60):
    """Send messages, then read replies until every request id has answered. Closing stdin first
    races the server's shutdown against its last reply on fast machines."""
    for m in msgs:
        proc.stdin.write(json.dumps(m) + "\n")
        proc.stdin.flush()
    want = {m["id"] for m in msgs if "id" in m}
    replies, end = {}, time.time() + timeout
    while want - set(replies) and time.time() < end:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("id") is not None:
            replies[r["id"]] = r
    proc.stdin.close()
    proc.kill()
    proc.wait()
    return replies
