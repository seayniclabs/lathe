"""Tests for the Lathe security module."""

import os
from pathlib import Path

import pytest

from lathe.security import (
    PathSecurityError,
    check_dependency,
    check_file_size,
    get_dependency_status,
    validate_input_path,
    validate_output_path,
)


@pytest.fixture
def sandbox(tmp_path):
    """Create a sandbox directory with a test file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")
    return tmp_path


class TestValidateInputPath:
    def test_valid_path(self, sandbox):
        result = validate_input_path(str(sandbox / "test.txt"), str(sandbox))
        assert result == (sandbox / "test.txt").resolve()

    def test_path_traversal_rejected(self, sandbox):
        with pytest.raises(PathSecurityError, match="escapes working directory"):
            validate_input_path(
                str(sandbox / "../../etc/passwd"), str(sandbox)
            )

    def test_absolute_escape_rejected(self, sandbox):
        with pytest.raises((PathSecurityError, FileNotFoundError)):
            validate_input_path("/etc/passwd", str(sandbox))

    def test_file_not_found(self, sandbox):
        with pytest.raises(FileNotFoundError):
            validate_input_path(str(sandbox / "nonexistent.txt"), str(sandbox))

    def test_directory_rejected(self, sandbox):
        subdir = sandbox / "subdir"
        subdir.mkdir()
        with pytest.raises(PathSecurityError, match="Not a file"):
            validate_input_path(str(subdir), str(sandbox))

    def test_symlink_escape_rejected(self, sandbox):
        # Create a symlink that points outside the sandbox
        link = sandbox / "escape_link"
        link.symlink_to("/etc")
        target = str(link / "hostname")
        with pytest.raises((PathSecurityError, FileNotFoundError)):
            validate_input_path(target, str(sandbox))

    def test_symlink_within_sandbox_allowed(self, sandbox):
        # Symlink to a file within the sandbox should work
        original = sandbox / "test.txt"
        link = sandbox / "link.txt"
        link.symlink_to(original)
        result = validate_input_path(str(link), str(sandbox))
        assert result == original.resolve()


class TestValidateOutputPath:
    def test_valid_output(self, sandbox):
        result = validate_output_path(str(sandbox / "output.txt"), str(sandbox))
        assert result == (sandbox / "output.txt").resolve()

    def test_output_traversal_rejected(self, sandbox):
        with pytest.raises(PathSecurityError, match="escapes working directory"):
            validate_output_path(
                str(sandbox / "../../tmp/evil.txt"), str(sandbox)
            )

    def test_creates_parent_directories(self, sandbox):
        out = validate_output_path(
            str(sandbox / "sub" / "dir" / "file.txt"), str(sandbox)
        )
        assert out.parent.exists()

    def test_nested_output(self, sandbox):
        result = validate_output_path(
            str(sandbox / "a" / "b" / "c.png"), str(sandbox)
        )
        assert str(result).startswith(str(sandbox.resolve()))


class TestCheckFileSize:
    def test_small_file_passes(self, sandbox):
        # test.txt is tiny, should not raise
        check_file_size(sandbox / "test.txt", max_mb=1)

    def test_large_file_rejected(self, sandbox):
        big = sandbox / "big.bin"
        # Create a file > 1MB
        big.write_bytes(b"\x00" * (2 * 1024 * 1024))
        with pytest.raises(ValueError, match="too large"):
            check_file_size(big, max_mb=1)


class TestOutputPathSymlinkEscape:
    def test_symlink_output_escape_rejected(self, sandbox):
        """A symlink pointing outside the sandbox is rejected for output paths."""
        # Create a symlink inside the sandbox that resolves outside it
        link = sandbox / "escape_link"
        link.symlink_to("/tmp")
        target = str(link / "evil_output.txt")
        with pytest.raises(PathSecurityError, match="escapes working directory"):
            validate_output_path(target, str(sandbox))

    def test_symlink_output_within_sandbox_allowed(self, sandbox):
        """A symlink resolving within the sandbox is allowed for output."""
        subdir = sandbox / "real_sub"
        subdir.mkdir()
        link = sandbox / "link_sub"
        link.symlink_to(subdir)
        result = validate_output_path(str(link / "out.txt"), str(sandbox))
        assert str(result).startswith(str(sandbox.resolve()))


class TestDecompressionBombGuard:
    def test_max_image_pixels_is_configured(self):
        """image_ops sets Image.MAX_IMAGE_PIXELS to prevent decompression bombs."""
        from PIL import Image
        # Importing image_ops should have already set the limit
        import lathe.image_ops  # noqa: F401
        assert Image.MAX_IMAGE_PIXELS is not None
        assert Image.MAX_IMAGE_PIXELS == 178_956_970


class TestDependencyChecks:
    def test_check_python_exists(self):
        # Python itself should always be findable
        assert check_dependency("python3") or check_dependency("python")

    def test_check_nonexistent_dep(self):
        assert check_dependency("nonexistent_binary_xyz") is False

    def test_get_dependency_status_structure(self):
        status = get_dependency_status()
        assert "ffmpeg" in status
        assert "tesseract" in status
        assert "ghostscript" in status
        for name, info in status.items():
            assert "available" in info
            assert "install_hint" in info
            assert isinstance(info["available"], bool)
