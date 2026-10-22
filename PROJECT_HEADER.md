# Lathe

**Type:** MCP server (free, MIT)  
**Status:** active  
**Owner:** Charlie  
**Last Updated:** 2026-10-22

## Purpose
Free media MCP server for images, video, OCR and PDFs (Pillow, ffmpeg-python, pytesseract, pypdf). Published on PyPI as `lathe-mcp`; repo github.com/seayniclabs/lathe.

## Current State
- **0.2.2 on PyPI (2026-10-19):** pins `mcp<2` (2.x removed FastMCP), which fixed the crash on a fresh install; a fresh `pip install` was verified working.
- One of the two MCPs in the free catalog on Bridge (with Bench), as of 2026-10-19.
- Kept active by Charlie 2026-10-20. Blueprint drafted 2026-10-22 (gate open on D-1, D-2).
- 2026-10-22: tests generate their own fixtures; a clean checkout passes 106/106.

## Next Steps
1. Charlie: decide D-1 (make all 16 tools free, recommended; the key check accepts any `SL-` key and there is no purchase page) and D-2 (MIT + public repo, recommended; README badge still says Proprietary). See `blueprint show lathe` (drafted 2026-10-22, gate open)
2. Watch for the next `mcp` major version and test before lifting the `<2` pin
