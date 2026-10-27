# Lathe
<!-- mcp-name: io.github.seayniclabs/lathe -->

Lathe is an MCP bundle for anyone who handles files and media. It gives an AI assistant local tools for images, PDFs, audio and video, and OCR, so the files never leave your machine.

It is a **bundle**: one server made of modules. Each module can be switched on or off. New modules arrive switched off, so an update never changes what your assistant can do until you choose to.

| Module | What it does | Status |
|---|---|---|
| `images` | Info, resize, convert, optimize, crop and thumbnail. Pillow, always available. | 0.3, ready |
| `pdf` | Info, text extraction (with OCR for scanned pages), merge, and rendering pages to images | 0.3, ready |
| `media` | Audio and video info, audio conversion, and a frame from a video (ffmpeg) | 0.3, ready |
| `ocr` | Read the text in an image (Tesseract) | 0.3, ready |

Lathe is free and MIT licensed. All 17 tools are included.

Lathe works with any MCP client: Claude Desktop, Claude Code, Cursor, VS Code, Sonique, Hermes, OpenClaw and others.

## Install

Lathe needs Python 3.11 or newer. With [uv](https://docs.astral.sh/uv/) you don't install anything ahead of time. Choose the extras for the modules you use:

```bash
uvx --from lathe-mcp lathe --version                  # images and media
uvx --from "lathe-mcp[pdf,ocr]" lathe --version       # with PDF and OCR
```

Or with pip:

```bash
pip install "lathe-mcp[pdf,ocr]"
```

Extras: `pdf` (pypdf), `ocr` (pytesseract), `full` (both). The images module needs nothing extra.

### System programs

Some tools call programs that Python cannot install for you. Lathe starts without them. The `lathe_modules` tool lists what is missing and the command for your platform.

| Program | Used by | macOS | Debian / Ubuntu |
|---|---|---|---|
| ffmpeg (includes ffprobe) | `media` | `brew install ffmpeg` | `apt install ffmpeg` |
| tesseract | `ocr`, and `pdf_extract_text` on scanned pages | `brew install tesseract` | `apt install tesseract-ocr` |
| ghostscript | `pdf_to_images` | `brew install ghostscript` | `apt install ghostscript` |

## Settings

Set these as environment variables in your MCP client's config, or in a config file. Lathe starts without any of them.

| Variable | Module | What it is |
|---|---|---|
| `LATHE_WORKING_DIR` | core | The folder Lathe reads from and writes to. Default: the folder the server starts in. |
| `LATHE_MAX_FILE_MB` | core | Largest input file, in MB. Default 500. |
| `LATHE_OCR_LANG` | ocr | Tesseract language code(s), e.g. `eng` or `eng+fra`. Default `eng`. |
| `LATHE_<MODULE>_ENABLED` | any | `false` turns a module off, e.g. `LATHE_MEDIA_ENABLED=false`. Default `true` for all four modules. |

**Config file (optional).** Lathe also reads `~/.config/lathe/config.toml`, or the file named by `LATHE_CONFIG`. Environment variables win over the file.

```toml
[core]
working_dir = "/Users/you/Pictures"

[ocr]
lang = "eng"

[media]
enabled = false
```

## Add it to your MCP client

Every client below runs Lathe as a local process over stdio. Put the `env` values only where you need them.

**Claude Desktop**: `claude_desktop_config.json` (Settings, Developer, Edit Config)

```json
{
  "mcpServers": {
    "lathe": {
      "command": "uvx",
      "args": ["--from", "lathe-mcp[pdf,ocr]", "lathe"],
      "env": { "LATHE_WORKING_DIR": "/path/to/your/files" }
    }
  }
}
```

**Claude Code**

```bash
claude mcp add lathe -e LATHE_WORKING_DIR=/path/to/your/files -- uvx --from "lathe-mcp[pdf,ocr]" lathe
```

**Cursor**: `~/.cursor/mcp.json`, or `.cursor/mcp.json` in a project

```json
{
  "mcpServers": {
    "lathe": {
      "command": "uvx",
      "args": ["--from", "lathe-mcp[pdf,ocr]", "lathe"],
      "env": { "LATHE_WORKING_DIR": "/path/to/your/files" }
    }
  }
}
```

**VS Code**: `.vscode/mcp.json` (note `"servers"`, not `"mcpServers"`)

```json
{
  "servers": {
    "lathe": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "lathe-mcp[pdf,ocr]", "lathe"],
      "env": { "LATHE_WORKING_DIR": "/path/to/your/files" }
    }
  }
}
```

**Sonique, Hermes, OpenClaw, and other clients**: any client that launches a stdio MCP server. Command `uvx`, arguments `["--from", "lathe-mcp[pdf,ocr]", "lathe"]`, plus the `env` values above.

**Over HTTP.** For clients that connect to a URL instead of starting a process:

```bash
lathe --transport http --port 8765
```

It serves streamable HTTP at `http://127.0.0.1:8765/mcp`. It listens only on your own machine by default. Put authentication in front of it before exposing it anywhere else.

## Tools

| Tool | What it does |
|---|---|
| `health` | Server version, working folder, and whether each external program is installed |
| `lathe_modules` | Which modules are on, what is missing (with the install command), and what each tool needs. Call this first. |
| `image_info` | Width, height, format, mode, size, and EXIF tags |
| `image_resize` | Resize by width, height or percentage, keeping the aspect ratio |
| `image_convert` | Convert to png, jpeg, webp, avif or bmp |
| `image_optimize` | Shrink for web delivery; metadata stripped unless `strip_metadata=false` |
| `image_crop` | Crop a rectangle |
| `image_thumbnail` | Fit inside a square |
| `pdf_info` | Page count, size, encryption, title, author |
| `pdf_extract_text` | Text of all or some pages; OCR for pages without a text layer; long text in parts |
| `pdf_merge` | Merge PDFs in order |
| `pdf_to_images` | Render pages to PNG or JPEG at a chosen DPI |
| `audio_info` | Duration, format, bitrate, sample rate, channels |
| `audio_convert` | Convert to mp3, wav, flac, aac or ogg |
| `video_info` | Duration, resolution, codec, frame rate, audio tracks |
| `video_thumbnail` | Save one frame at a time in seconds |
| `ocr_image` | Text from an image; long text in parts |

Every tool returns structured data with a published schema. Long text comes in parts: pass `next_offset` back as `offset`. Errors always read `lathe.<module>.<code>: <message> Fix: <hint>`.

## Files and safety

- **Working folder.** Relative paths resolve against `LATHE_WORKING_DIR`. Inputs and outputs must stay inside it. Symlinks that point outside are refused.
- **Nothing is overwritten by accident.** An output that already exists is refused unless the call passes `overwrite=true`. An output can never be the input file.
- **Writes are atomic.** A file is written under a temporary name and moved into place, so a failure never leaves a half-written file.
- **Local only.** Lathe runs on your machine, sends nothing anywhere and keeps no data.
- **Size limit.** Inputs over `LATHE_MAX_FILE_MB` (500 MB by default) are refused.

## Develop

```bash
uv venv -p 3.11 .venv && uv pip install -p .venv/bin/python -e '.[dev]'
.venv/bin/pytest -q
```

The tests generate their own fixtures. Tests that need ffmpeg, tesseract or ghostscript are skipped when the program is missing.

## License

MIT. Published by Seaynic Labs.
