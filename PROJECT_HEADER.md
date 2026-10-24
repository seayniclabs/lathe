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

1. [Batch 2] Cut 0.3.0: all 16 tools free, SL- key gate removed (D-1), MIT in LICENSE, README badge and pyproject (D-2), git tag + GitHub release (lathe-1, lathe-2)
2. [Batch 2] README: `uvx lathe-mcp` one-liner and Claude Code / Claude Desktop / Cursor config blocks (lathe-3)
3. [Batch 2] Report the package version in serverInfo, not the mcp SDK version (lathe-5)
4. [Batch 2] server.json + MCP registry, Smithery and Glama as 'Lathe — local media tools' (lathe-4)
5. Watch for the next `mcp` major version and test before lifting the `<2` pin

