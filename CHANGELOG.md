# Changelog

Lathe follows [semantic versioning](https://semver.org). New modules ship switched off.

## 0.4.0

Bundle release: tools, skills and trust features in one install.

**New tools**

- `batch_process` (new `batch` module, off by default): one operation over every file matching a glob in a folder. Operations: `image_resize`, `image_convert`, `image_optimize`, `image_thumbnail`, `pdf_to_images`, `audio_convert`. A dry run is the default and returns the plan. A real run of more than one file asks the person to approve the plan, once. Typed result per file. Inputs are never overwritten.
- `scrub_metadata` (new `privacy` module, off by default): `inspect` lists a photo's or PDF's metadata and whether it has GPS coordinates. `scrub` writes a clean copy: EXIF, GPS, ICC and XMP for images; Author, Creator, Producer and XMP for PDFs.
- `pdf_split` (pages per part) and `pdf_compress` (lossless: content streams and duplicate objects) in the `pdf` module.
- `video_trim` (stream copy, cuts on keyframes) and `video_to_gif` (up to 30 seconds, palette-optimized) in the `media` module.

**Approval**

- Writing tools create one new file per call and never overwrite an existing file unless `overwrite=true`. None of them asks for approval.
- `batch_process` asks the person once to approve a run of two or more files. The prompt lists the output folder, the overwrite flag, the file count and up to ten file names, each quoted and cleaned. `LATHE_BATCH_PREAPPROVED=true` skips the prompt. A client that cannot show prompts gets `approval_unavailable`, which names the fix.
- Every batch request, approval, decline and refusal goes to a local log at `~/.local/state/lathe/approvals.jsonl`. File contents and file names are not logged. Set `LATHE_APPROVAL_LOG` to move it.
- Output folders and output names that are symbolic links are refused, and every output must resolve inside the working folder.

**Skills**

- Four skills, served as Agent Skills folders in `skills/` and as MCP prompts and resources: `getting-started`, `pdf`, `pdf-forms` and `web-image-prep`. All are MIT licensed and written by Seaynic Labs. No third-party skills are included.

**Discovery, checks and packaging**

- `lathe_modules` lists the skills, the publisher and the homepage.
- `lathe --doctor` checks the working folder, Pillow and each enabled module's pieces. It prints the install command for each FIX line and exits 1 when something needs fixing.
- `tool-manifest.lock.json` locks every tool description, prompt and the server instructions. CI fails when they change without the lock changing.
- `scripts/security_card.py` prints the README security card from the live server. CI checks it is current.
- The Claude Code plugin manifest pins `lathe-mcp[pdf,ocr]==0.4.0`.
- `SECURITY.md` and `CREDITS.md` added.

**Compatibility**

- The 17 tools from 0.3.0 keep their names, arguments and results. Four new tools (`pdf_split`, `pdf_compress`, `video_trim`, `video_to_gif`) arrive in modules that are already on. `batch_process` and `scrub_metadata` arrive switched off.
- The `ModulesResult` gains `skills`, `publisher` and `homepage` fields.

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
