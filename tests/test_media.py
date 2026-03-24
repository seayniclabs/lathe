"""Tests for Lathe media (audio/video) operations."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lathe.media_ops import audio_info


FIXTURES = Path(__file__).parent / "fixtures"


class TestAudioInfo:
    @pytest.mark.requires_ffmpeg
    def test_audio_info_happy_path(self):
        """audio_info returns metadata for a valid WAV file."""
        info = audio_info(FIXTURES / "audio.wav")
        assert info["duration"] > 0
        assert info["format"] is not None
        assert info["sample_rate"] == 44100
        assert info["channels"] == 1

    @pytest.mark.requires_ffmpeg
    def test_audio_info_has_file_size(self):
        info = audio_info(FIXTURES / "audio.wav")
        assert info["file_size"] > 0


class TestMissingDependencies:
    def test_ffmpeg_missing_raises(self):
        """audio_convert raises RuntimeError when ffmpeg is absent."""
        from lathe.media_ops import audio_convert

        with patch("lathe.media_ops.check_dependency", return_value=False):
            with pytest.raises(RuntimeError, match="ffmpeg is required"):
                audio_convert(FIXTURES / "audio.wav", Path("/tmp/out.mp3"), "mp3")

    def test_ffprobe_missing_raises(self):
        """audio_info raises RuntimeError when ffprobe is absent."""
        with patch("lathe.media_ops.check_dependency", return_value=False):
            with pytest.raises(RuntimeError, match="ffprobe is required"):
                audio_info(FIXTURES / "audio.wav")

    def test_tesseract_missing_raises(self):
        """OCR raises RuntimeError when tesseract is absent."""
        from lathe.server import check_dependency as _orig
        from lathe import server

        with patch.object(server, "check_dependency", return_value=False):
            with pytest.raises(RuntimeError, match="tesseract is required"):
                server.ocr_image(str(FIXTURES / "text_image.png"))

    def test_ghostscript_missing_raises(self):
        """pdf_to_images raises RuntimeError when ghostscript is absent."""
        from lathe.pdf_ops import to_images

        with patch("lathe.pdf_ops.check_dependency", return_value=False):
            with pytest.raises(RuntimeError, match="Ghostscript is required"):
                to_images(FIXTURES / "audio.wav", Path("/tmp/out"))
