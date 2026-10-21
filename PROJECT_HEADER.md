# Lathe

**Type:** MCP server (free, MIT)  
**Status:** active  
**Owner:** Charlie  
**Last Updated:** 2026-10-20

## Purpose
Free media MCP server for images, video, OCR and PDFs (Pillow, ffmpeg-python, pytesseract, pypdf). Published on PyPI as `lathe-mcp`; repo github.com/seayniclabs/lathe.

## Current State
- **0.2.2 on PyPI (2026-10-19):** pins `mcp<2` (2.x removed FastMCP), which fixed the crash on a fresh install; a fresh `pip install` was verified working.
- One of the two MCPs in the free catalog on Bridge (with Bench), as of 2026-10-19.
- Kept active by Charlie 2026-10-20. No blueprint yet.

## Next Steps
1. Write the blueprint (`blueprint new lathe`): who it's for, what comes after 0.2.2, and how the free catalog promotes it
2. Watch for the next `mcp` major version and test before lifting the `<2` pin
