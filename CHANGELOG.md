# Changelog

Lathe follows [semantic versioning](https://semver.org). New modules ship switched off.

## 0.3.0

- `lathe-mcp` is now also a command, so `uvx lathe-mcp` works (as MCP registry installs run it). `lathe` still works.
- Security: ffmpeg and ffprobe only read local files (`-protocol_whitelist file,pipe`), and playlist, concat and manifest inputs are refused, so a crafted media file can't make Lathe fetch URLs or read other files.
- Free: all tools are included. The license-key gate and the upgrade tool are gone.
- MIT everywhere: `LICENSE`, the README and `pyproject.toml` agree.
- Four modules: `images` (Pillow), `pdf` (pypdf, ghostscript), `media` (ffmpeg, ffprobe) and `ocr` (pytesseract, tesseract). Each can be switched on or off with `LATHE_<MODULE>_ENABLED`.
- A module whose Python extra or system program is missing still starts. `lathe_modules` reports it with the install command, and its tools return `lathe.<module>.unavailable` naming the fix.
- `lathe_modules` discovery tool, and a `health` tool that lists each external program.
- Every tool returns typed, structured results with an output schema. Long text comes in parts (`offset`, `max_chars`, `next_offset`).
- Safer files: relative paths resolve inside the working directory, symlinks that escape it are refused, an output never replaces an input, and no output replaces an existing file without `overwrite=true`. Writes are atomic.
- Errors read `lathe.<module>.<code>: <message> Fix: <hint>`.
- The server reports its own version in `serverInfo` (it used to report the mcp SDK's version).
- Runs over stdio or streamable HTTP. Starts with no settings.
- Tools: 17 (was 8 unlicensed, 16 with a key).
