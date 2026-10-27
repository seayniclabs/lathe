# Lathe

**Type:** MCP bundle (free, MIT)
**Status:** active
**Publisher:** Seaynic Labs
**Version:** 0.3.0 (release pending)

## Purpose
Local MCP tools for files and media: images, PDFs, audio and video, and OCR. Published on PyPI as `lathe-mcp`; source at github.com/seayniclabs/lathe.

## Current state
- 0.2.2 is on PyPI (pins `mcp<2`). 0.3.0 makes all 17 tools free, drops the license-key gate, uses MIT throughout, adds the module switches, and brings the bundle to the bundle standard.
- Verified locally for 0.3.0: 44 tests pass with ffmpeg, tesseract and ghostscript installed, and 36 pass with them absent.

## Next steps
1. Tag and release 0.3.0 once the public repository is reset to a fresh history.
2. Publish the registry entry from `server.json`.
3. Watch for the next `mcp` major version and test before lifting the `<2` pin.
