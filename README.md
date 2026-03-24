# Lathe — File & Media Processing MCP Server

Transforming raw files into precision output — the Swiss army knife for file processing.

![License: Proprietary](https://img.shields.io/badge/license-proprietary-D97706)

---

## What It Does

Lathe is an MCP server that gives AI assistants direct access to file and media processing operations. 16 tools across four categories handle the most common file transformation tasks: image manipulation, PDF operations, audio/video processing, and OCR text extraction.

Install the core package for image processing, or install with extras to unlock PDF, media, and OCR capabilities.

---

## Tool Reference

### Image

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `image_info` | Get image metadata (dimensions, format, mode, EXIF) | `input_path` |
| `image_resize` | Resize with aspect ratio preservation | `input_path`, `output_path`, `width`, `height`, `percentage` |
| `image_convert` | Convert format (png, jpeg, webp, avif, bmp) | `input_path`, `output_path`, `format` |
| `image_optimize` | Optimize for web delivery | `input_path`, `output_path`, `quality`, `strip_metadata` |
| `image_crop` | Crop a rectangular region | `input_path`, `output_path`, `x`, `y`, `width`, `height` |
| `image_thumbnail` | Generate a square-fit thumbnail | `input_path`, `output_path`, `size` |

### PDF

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `pdf_info` | Get PDF metadata (pages, title, author, encryption) | `input_path` |
| `pdf_extract_text` | Extract text, with OCR fallback | `input_path`, `pages` |
| `pdf_merge` | Merge multiple PDFs into one | `input_paths`, `output_path` |
| `pdf_to_images` | Convert pages to images (requires ghostscript) | `input_path`, `output_dir`, `pages`, `format` |

### Audio / Video

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `audio_convert` | Convert audio format (mp3, wav, flac, aac, ogg) | `input_path`, `output_path`, `format` |
| `audio_info` | Get audio metadata (duration, bitrate, sample rate) | `input_path` |
| `video_thumbnail` | Extract a frame from video as image | `input_path`, `output_path`, `timestamp` |
| `video_info` | Get video metadata (duration, resolution, codec) | `input_path` |

### OCR

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `ocr_image` | Extract text from image via Tesseract | `input_path` |

### Utility

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `health` | Server status, version, dependency availability | — |

---

## Installation

Core install (image tools only):

```bash
pip install lathe-mcp
```

Full install (PDF, audio/video, OCR):

```bash
pip install "lathe-mcp[full]"
```

### System Dependencies

Some tools require external binaries. Install only what you need:

| Dependency | Required For | Install |
|------------|-------------|---------|
| ffmpeg | Audio/video tools | `brew install ffmpeg` / `apt install ffmpeg` |
| tesseract | OCR tools | `brew install tesseract` / `apt install tesseract-ocr` |
| ghostscript | `pdf_to_images` | `brew install ghostscript` / `apt install ghostscript` |

The `health` tool reports which dependencies are available at runtime.

---

## Usage

Run the server directly:

```bash
lathe
```

Or via the MCP CLI:

```bash
mcp run lathe
```

### Claude Code

```bash
claude mcp add lathe -- /path/to/venv/bin/lathe
```

### Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lathe": {
      "command": "/path/to/venv/bin/lathe",
      "env": {
        "LATHE_WORKING_DIR": "/path/to/allowed/directory"
      }
    }
  }
}
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LATHE_WORKING_DIR` | Root directory for all file operations | Current working directory |

All input and output paths are resolved relative to and constrained within `LATHE_WORKING_DIR`.

---

## Security

- **Sandboxed file access** — all paths validated against `LATHE_WORKING_DIR`
- **Path traversal protection** — `../` and absolute paths outside the sandbox are rejected
- **Symlink escape detection** — symlinks resolving outside the working directory are blocked
- **Decompression bomb guard** — Pillow's built-in protections are active
- **File size limits** — 500 MB maximum per input file

---

## Development

```bash
git clone https://github.com/seayniclabs/lathe.git
cd lathe
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test,full]"
python -m pytest tests/ -q
```

---

## License

Proprietary. Copyright (c) 2026 Seaynic Labs LLC. All rights reserved.

See [LICENSE](LICENSE) for details.
