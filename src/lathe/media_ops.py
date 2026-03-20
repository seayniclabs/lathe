"""Audio and video processing via ffmpeg/ffprobe.

All ffmpeg calls use subprocess with list arguments (never shell=True).
Operations gracefully report when ffmpeg is not installed.
"""

import json
import subprocess
from pathlib import Path

from .security import check_dependency


def _require_ffmpeg():
    """Raise a clear error if ffmpeg is not available."""
    if not check_dependency("ffmpeg"):
        raise RuntimeError(
            "ffmpeg is required for audio/video operations. "
            "Install with: brew install ffmpeg (macOS) / apt install ffmpeg (Debian)"
        )


def _require_ffprobe():
    """Raise a clear error if ffprobe is not available."""
    if not check_dependency("ffprobe"):
        raise RuntimeError(
            "ffprobe is required for media info. "
            "It is included with ffmpeg: brew install ffmpeg (macOS) / apt install ffmpeg (Debian)"
        )


def _run_ffprobe(input_path: Path) -> dict:
    """Run ffprobe and return parsed JSON output."""
    _require_ffprobe()

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    return json.loads(result.stdout)


def audio_convert(input_path: Path, output_path: Path, fmt: str) -> dict:
    """Convert audio to a different format.

    Args:
        input_path: Source audio file.
        output_path: Destination file.
        fmt: Target format (mp3, wav, flac, aac, ogg).

    Returns:
        Dict with conversion details.
    """
    _require_ffmpeg()

    codec_map = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "flac": "flac",
        "aac": "aac",
        "ogg": "libvorbis",
    }

    fmt_lower = fmt.lower()
    if fmt_lower not in codec_map:
        raise ValueError(f"Unsupported audio format: {fmt}. Use: {', '.join(codec_map)}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-acodec", codec_map[fmt_lower],
        str(output_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")

    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "format": fmt_lower,
        "output_size": output_path.stat().st_size,
    }


def audio_info(input_path: Path) -> dict:
    """Extract audio file metadata using ffprobe."""
    probe = _run_ffprobe(input_path)

    fmt_info = probe.get("format", {})
    audio_stream = None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    info = {
        "duration": float(fmt_info.get("duration", 0)),
        "format": fmt_info.get("format_name"),
        "bitrate": int(fmt_info.get("bit_rate", 0)),
        "file_size": int(fmt_info.get("size", 0)),
    }

    if audio_stream:
        info["sample_rate"] = int(audio_stream.get("sample_rate", 0))
        info["channels"] = audio_stream.get("channels", 0)
        info["codec"] = audio_stream.get("codec_name")

    return info


def video_thumbnail(
    input_path: Path,
    output_path: Path,
    timestamp: float = 0,
) -> dict:
    """Extract a single frame from a video as an image.

    Args:
        input_path: Source video file.
        output_path: Output image file.
        timestamp: Time in seconds to extract frame from.

    Returns:
        Dict with extraction details.
    """
    _require_ffmpeg()

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", str(input_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail extraction failed: {result.stderr}")

    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "timestamp": timestamp,
        "output_size": output_path.stat().st_size,
    }


def video_info(input_path: Path) -> dict:
    """Extract video file metadata using ffprobe."""
    probe = _run_ffprobe(input_path)

    fmt_info = probe.get("format", {})
    video_stream = None
    audio_tracks = []

    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio":
            audio_tracks.append({
                "codec": stream.get("codec_name"),
                "channels": stream.get("channels"),
                "sample_rate": stream.get("sample_rate"),
            })

    info = {
        "duration": float(fmt_info.get("duration", 0)),
        "format": fmt_info.get("format_name"),
        "bitrate": int(fmt_info.get("bit_rate", 0)),
        "file_size": int(fmt_info.get("size", 0)),
        "audio_tracks": audio_tracks,
    }

    if video_stream:
        info["width"] = video_stream.get("width")
        info["height"] = video_stream.get("height")
        info["resolution"] = f"{video_stream.get('width')}x{video_stream.get('height')}"
        info["codec"] = video_stream.get("codec_name")
        info["fps"] = video_stream.get("r_frame_rate")

    return info
