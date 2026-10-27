"""Audio and video tools. They call the ffmpeg and ffprobe programs; nothing goes through a shell.

Note: no ``from __future__ import annotations`` here (see images.py).
"""

import json
import subprocess
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from ..errors import LatheError
from ..paths import atomic_write
from . import FFMPEG, FFPROBE, Module, Setting, ToolSpec, READ, WRITE

AUDIO_CODEC = {"mp3": "libmp3lame", "wav": "pcm_s16le", "flac": "flac", "aac": "aac", "ogg": "libvorbis"}
AUDIO_EXT = {"mp3": {".mp3"}, "wav": {".wav"}, "flac": {".flac"}, "aac": {".aac", ".m4a"}, "ogg": {".ogg", ".oga"}}
FRAME_EXT = {".png", ".jpg", ".jpeg"}
GIF_MAX_SECONDS = 30
TIMEOUT_CONVERT = 600
TIMEOUT_FRAME = 60
TIMEOUT_PROBE = 30


class AudioInfo(BaseModel):
    duration_seconds: float
    format_name: str | None
    bitrate: int
    file_bytes: int
    codec: str | None
    sample_rate: int | None
    channels: int | None


class AudioConvert(BaseModel):
    output_path: str
    output_bytes: int
    format: str


class VideoFrame(BaseModel):
    output_path: str
    output_bytes: int
    timestamp_seconds: float


class AudioTrack(BaseModel):
    codec: str | None
    channels: int | None
    sample_rate: str | None


class VideoInfo(BaseModel):
    duration_seconds: float
    format_name: str | None
    bitrate: int
    file_bytes: int
    width: int | None
    height: int | None
    codec: str | None
    fps: str | None = Field(description="Frame rate as a fraction, e.g. 30000/1001.")
    audio_tracks: list[AudioTrack]


class VideoTrim(BaseModel):
    output_path: str
    output_bytes: int
    start_seconds: float
    end_seconds: float | None = Field(description="None when the trim runs to the end of the file.")
    source_duration_seconds: float
    note: str = "Stream copy: cuts land on the nearest keyframe, so the start can be a little early."


class VideoGif(BaseModel):
    output_path: str
    output_bytes: int
    start_seconds: float
    duration_seconds: float
    width: int
    fps: int


_PLAYLIST_MARKERS = (b"#EXTM3U", b"ffconcat", b"[playlist]", b"<?xml", b"<smil")


def _refuse_playlists(path: str) -> None:
    """Playlist, concat and manifest files make ffmpeg open other files or URLs they name. Refuse them."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(512).lstrip(b"\xef\xbb\xbf \t\r\n")
    except OSError:
        return  # a missing input is reported by ffmpeg itself
    if head.lower().startswith(tuple(m.lower() for m in _PLAYLIST_MARKERS)) or head.startswith(b"file "):
        raise LatheError("media", "unsupported_input", "playlist, concat and manifest files are not accepted.",
                         "pass a single media file, e.g. .mp4, .mov, .mp3 or .wav.")


def _run(cmd: list[str], timeout: int, what: str) -> subprocess.CompletedProcess:
    # Inputs are the arguments after -i (ffmpeg) or the last argument (ffprobe).
    inputs = [cmd[i + 1] for i, a in enumerate(cmd[:-1]) if a == "-i"] if cmd[0] == "ffmpeg" else [cmd[-1]]
    for path in inputs:
        _refuse_playlists(path)
    # Local files only: no http(s), tcp, data: or other protocols, whatever the input names inside it.
    cmd = [cmd[0], "-protocol_whitelist", "file,pipe", *cmd[1:]]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise LatheError("media", "failed", f"{what} failed: {result.stderr.strip()[-300:]}",
                         "check the input file is a complete media file.")
    return result


def _probe(path: Path) -> dict:
    result = _run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                  TIMEOUT_PROBE, "ffprobe")
    return json.loads(result.stdout or "{}")


def _number(value, cast, default):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


# --- operations on resolved paths. The tools below and batch_process both call these. ---

def op_audio_convert(src: Path, out: Path, format: str) -> dict:
    if out.suffix.lower() not in AUDIO_EXT[format]:
        raise LatheError("media", "bad_input", f"output extension {out.suffix!r} does not match {format}.",
                         f"name the output with one of {', '.join(sorted(AUDIO_EXT[format]))}.")

    def write(tmp: Path) -> None:
        _run(["ffmpeg", "-nostdin", "-y", "-i", str(src), "-vn", "-acodec", AUDIO_CODEC[format], str(tmp)],
             TIMEOUT_CONVERT, "ffmpeg conversion")

    atomic_write(out, write)
    return {"output_path": str(out), "output_bytes": out.stat().st_size, "format": format}


def op_video_trim(src: Path, out: Path, start: float, end: float | None) -> dict:
    probe = _probe(src)
    duration = _number((probe.get("format") or {}).get("duration"), float, 0.0)
    if duration and start >= duration:
        raise LatheError("media", "bad_input", f"start {start}s is at or past the end of the {duration:.1f}s file.",
                         "pick a start time inside the file.")
    length = None if end is None else round(end - start, 3)
    cmd = ["ffmpeg", "-nostdin", "-y", "-ss", str(start), "-i", str(src)]
    if length is not None:
        cmd += ["-t", str(length)]
    cmd += ["-c", "copy"]

    def write(tmp: Path) -> None:
        _run([*cmd, str(tmp)], TIMEOUT_CONVERT, "ffmpeg trim")

    atomic_write(out, write)
    return {"output_path": str(out), "output_bytes": out.stat().st_size, "start_seconds": start,
            "end_seconds": end, "source_duration_seconds": duration}


def op_video_to_gif(src: Path, out: Path, start: float, duration: float, width: int, fps: int) -> dict:
    graph = (f"[0:v]fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
             "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer")
    cmd = ["ffmpeg", "-nostdin", "-y", "-ss", str(start), "-i", str(src), "-t", str(duration),
           "-an", "-filter_complex", graph]

    def write(tmp: Path) -> None:
        _run([*cmd, str(tmp)], TIMEOUT_CONVERT, "ffmpeg gif")

    atomic_write(out, write)
    return {"output_path": str(out), "output_bytes": out.stat().st_size, "start_seconds": start,
            "duration_seconds": duration, "width": width, "fps": fps}


_TOOLS = (
    ToolSpec("audio_info", "Audio metadata: duration, format, bitrate, sample rate, channels and codec.",
             requires=(FFPROBE,)),
    ToolSpec("audio_convert", "Convert audio to mp3, wav, flac, aac or ogg. A video input keeps only its audio. "
             "The output extension must match the format.", requires=(FFMPEG,), annotations=WRITE),
    ToolSpec("video_info", "Video metadata: duration, resolution, codec, frame rate, bitrate and audio tracks.",
             requires=(FFPROBE,)),
    ToolSpec("video_thumbnail", "Save one frame of a video as a PNG or JPEG, at a time in seconds.",
             requires=(FFMPEG,), annotations=WRITE),
    ToolSpec("video_trim", "Cut a section out of a video into a new file (stream copy, so it is fast and lossless; "
             "cuts land on keyframes). Never overwrites unless overwrite=true.",
             requires=(FFMPEG, FFPROBE), annotations=WRITE),
    ToolSpec("video_to_gif", "Make an animated GIF from part of a video (up to 30 seconds, palette-optimized). "
             "Writes one new file; never overwrites unless overwrite=true.",
             requires=(FFMPEG,), annotations=WRITE),
)


class MediaModule(Module):
    name = "media"
    summary = "Audio and video files: info, audio conversion, a frame, trim, GIF. Needs ffmpeg and ffprobe."
    settings: tuple[Setting, ...] = ()
    tools = _TOOLS

    def register(self, mcp, config) -> None:
        self.config = config
        tool = self.tool

        @tool(mcp, "audio_info")
        def audio_info(input_path: str) -> AudioInfo:
            src = self.input_file(input_path)
            probe = _probe(src)
            fmt = probe.get("format", {})
            stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None)
            if stream is None:
                raise LatheError("media", "no_audio_stream", f"{src.name} has no audio track.",
                                 "pass an audio file or a video with sound.")
            return AudioInfo(
                duration_seconds=_number(fmt.get("duration"), float, 0.0),
                format_name=fmt.get("format_name"),
                bitrate=_number(fmt.get("bit_rate"), int, 0),
                file_bytes=_number(fmt.get("size"), int, src.stat().st_size),
                codec=stream.get("codec_name"),
                sample_rate=_number(stream.get("sample_rate"), int, None),
                channels=stream.get("channels"),
            )

        @tool(mcp, "audio_convert")
        def audio_convert(input_path: str, output_path: str,
                          format: Literal["mp3", "wav", "flac", "aac", "ogg"], overwrite: bool = False) -> AudioConvert:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            return AudioConvert(**op_audio_convert(src, out, format))

        @tool(mcp, "video_info")
        def video_info(input_path: str) -> VideoInfo:
            src = self.input_file(input_path)
            probe = _probe(src)
            fmt = probe.get("format", {})
            streams = probe.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), None)
            tracks = [AudioTrack(codec=s.get("codec_name"), channels=s.get("channels"), sample_rate=s.get("sample_rate"))
                      for s in streams if s.get("codec_type") == "audio"][:16]
            if video is None:
                raise LatheError("media", "no_video_stream", f"{src.name} has no video track.",
                                 "use audio_info for audio files.")
            return VideoInfo(
                duration_seconds=_number(fmt.get("duration"), float, 0.0),
                format_name=fmt.get("format_name"),
                bitrate=_number(fmt.get("bit_rate"), int, 0),
                file_bytes=_number(fmt.get("size"), int, src.stat().st_size),
                width=video.get("width"), height=video.get("height"), codec=video.get("codec_name"),
                fps=video.get("r_frame_rate"), audio_tracks=tracks,
            )

        @tool(mcp, "video_thumbnail")
        def video_thumbnail(input_path: str, output_path: str,
                            timestamp: Annotated[float, Field(ge=0)] = 0.0, overwrite: bool = False) -> VideoFrame:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            if out.suffix.lower() not in FRAME_EXT:
                raise LatheError("media", "bad_input", f"output extension {out.suffix!r} is not an image type.",
                                 "use .png, .jpg or .jpeg.")

            def write(tmp: Path) -> None:
                _run(["ffmpeg", "-nostdin", "-y", "-ss", str(timestamp), "-i", str(src), "-frames:v", "1",
                      "-q:v", "2", str(tmp)], TIMEOUT_FRAME, "frame extraction")

            atomic_write(out, write)
            return VideoFrame(output_path=str(out), output_bytes=out.stat().st_size, timestamp_seconds=timestamp)

        @tool(mcp, "video_trim")
        def video_trim(input_path: str, output_path: str,
                             start: Annotated[float, Field(ge=0)] = 0.0,
                             end: Annotated[float | None, Field(ge=0)] = None, overwrite: bool = False) -> VideoTrim:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            if end is not None and end <= start:
                raise LatheError("media", "bad_input", f"end {end}s must be after start {start}s.",
                                 "set end to a time later than start, or leave it out to run to the end.")
            return VideoTrim(**op_video_trim(src, out, start, end))

        @tool(mcp, "video_to_gif")
        def video_to_gif(input_path: str, output_path: str,
                               start: Annotated[float, Field(ge=0)] = 0.0,
                               duration: Annotated[float, Field(gt=0, le=GIF_MAX_SECONDS)] = 5.0,
                               width: Annotated[int, Field(ge=16, le=1280)] = 480,
                               fps: Annotated[int, Field(ge=1, le=30)] = 10,
                               overwrite: bool = False) -> VideoGif:
            src = self.input_file(input_path)
            out = self.output_file(output_path, overwrite, inputs=[src])
            if out.suffix.lower() != ".gif":
                raise LatheError("media", "bad_input", f"output extension {out.suffix!r} is not .gif.",
                                 "name the output with .gif.")
            return VideoGif(**op_video_to_gif(src, out, start, duration, width, fps))
