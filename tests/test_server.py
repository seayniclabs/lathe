"""Tests for Lathe MCP server helpers and health tool."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lathe import __version__
from lathe.security import PathSecurityError


class TestHealth:
    def test_health_returns_status(self):
        from lathe.server import health

        result = health()
        assert result["status"] == "ok"

    def test_health_returns_version(self):
        from lathe.server import health

        result = health()
        assert result["version"] == __version__

    def test_health_returns_working_dir(self):
        from lathe.server import health

        result = health()
        assert "working_dir" in result
        assert isinstance(result["working_dir"], str)

    def test_health_returns_dependency_structure(self):
        from lathe.server import health

        result = health()
        deps = result["dependencies"]
        assert "ffmpeg" in deps
        assert "tesseract" in deps
        assert "ghostscript" in deps
        for name, info in deps.items():
            assert "available" in info
            assert "install_hint" in info


class TestInputHelper:
    def test_input_validates_and_checks_size(self, tmp_path):
        """_input chains path validation + size check."""
        test_file = tmp_path / "valid.txt"
        test_file.write_text("hello")

        from lathe.server import _input, WORKING_DIR
        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            result = _input(str(test_file))
            assert result == test_file.resolve()
        finally:
            srv.WORKING_DIR = original

    def test_input_rejects_traversal(self, tmp_path):
        """_input rejects paths that escape the working directory."""
        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            from lathe.server import _input

            with pytest.raises(PathSecurityError):
                _input(str(tmp_path / "../../etc/passwd"))
        finally:
            srv.WORKING_DIR = original

    def test_input_rejects_missing_file(self, tmp_path):
        """_input raises FileNotFoundError for nonexistent files."""
        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            from lathe.server import _input

            with pytest.raises(FileNotFoundError):
                _input(str(tmp_path / "ghost.txt"))
        finally:
            srv.WORKING_DIR = original

    def test_input_rejects_oversized_file(self, tmp_path):
        """_input rejects files exceeding the size limit."""
        big = tmp_path / "big.bin"
        big.write_bytes(b"\x00" * (501 * 1024 * 1024))

        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            from lathe.server import _input

            with pytest.raises(ValueError, match="too large"):
                _input(str(big))
        finally:
            srv.WORKING_DIR = original


class TestOutputHelper:
    def test_output_validates_path(self, tmp_path):
        """_output chains path validation for output files."""
        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            from lathe.server import _output

            result = _output(str(tmp_path / "out.png"))
            assert result == (tmp_path / "out.png").resolve()
        finally:
            srv.WORKING_DIR = original

    def test_output_rejects_traversal(self, tmp_path):
        """_output rejects output paths that escape the working directory."""
        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            from lathe.server import _output

            with pytest.raises(PathSecurityError):
                _output(str(tmp_path / "../../tmp/evil.txt"))
        finally:
            srv.WORKING_DIR = original

    def test_output_creates_parent_dirs(self, tmp_path):
        """_output creates parent directories if they don't exist."""
        import lathe.server as srv

        original = srv.WORKING_DIR
        try:
            srv.WORKING_DIR = str(tmp_path)
            from lathe.server import _output

            result = _output(str(tmp_path / "sub" / "dir" / "file.txt"))
            assert result.parent.exists()
        finally:
            srv.WORKING_DIR = original
