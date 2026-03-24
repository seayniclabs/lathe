"""Tests for freemium tool gating.

These tests verify that:
- Free mode only exposes image tools + health + upgrade_info
- Licensed mode exposes all 16 tools
- The health tool reports the correct tier and tool count
"""

import importlib
import os
import sys
from unittest.mock import patch

import pytest


def _reload_server_with_license(licensed: bool):
    """Reload the server module with or without a license.

    Returns the reloaded server module. Cleans up cached modules so
    the module-level gating code re-executes.
    """
    env = {**os.environ}
    if licensed:
        env["LATHE_LICENSE_KEY"] = "SL-TEST-0000"
    else:
        env.pop("LATHE_LICENSE_KEY", None)

    with patch.dict(os.environ, env, clear=True):
        # Remove cached server module so it re-evaluates _licensed
        for mod_name in list(sys.modules):
            if mod_name.startswith("lathe.server"):
                del sys.modules[mod_name]

        import lathe.server as srv
        importlib.reload(srv)
        return srv


FREE_TOOLS = {
    "health", "image_info", "image_resize", "image_convert",
    "image_optimize", "image_crop", "image_thumbnail", "upgrade_info",
}

LICENSED_TOOLS = {
    "health", "image_info", "image_resize", "image_convert",
    "image_optimize", "image_crop", "image_thumbnail",
    "pdf_info", "pdf_extract_text", "pdf_merge", "pdf_to_images",
    "audio_convert", "audio_info",
    "video_thumbnail", "video_info",
    "ocr_image",
}


class TestFreeMode:
    def test_free_mode_tools(self):
        srv = _reload_server_with_license(False)
        tool_names = {t.name for t in srv.mcp._tool_manager.list_tools()}
        assert tool_names == FREE_TOOLS

    def test_free_health_reports_free_tier(self):
        srv = _reload_server_with_license(False)
        result = srv.health()
        assert result["tier"] == "free"
        assert result["tools_available"] == len(FREE_TOOLS)

    def test_free_upgrade_info_has_purchase_url(self):
        srv = _reload_server_with_license(False)
        result = srv.upgrade_info()
        assert result["current_tier"] == "free"
        assert "seayniclabs.com" in result["purchase_url"]
        assert len(result["paid_tools"]) == 9


class TestLicensedMode:
    def test_licensed_mode_tools(self):
        srv = _reload_server_with_license(True)
        tool_names = {t.name for t in srv.mcp._tool_manager.list_tools()}
        assert tool_names == LICENSED_TOOLS

    def test_licensed_health_reports_licensed_tier(self):
        srv = _reload_server_with_license(True)
        result = srv.health()
        assert result["tier"] == "licensed"
        assert result["tools_available"] == len(LICENSED_TOOLS)

    def test_no_upgrade_info_when_licensed(self):
        srv = _reload_server_with_license(True)
        tool_names = {t.name for t in srv.mcp._tool_manager.list_tools()}
        assert "upgrade_info" not in tool_names
