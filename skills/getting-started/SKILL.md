---
name: getting-started
description: Set up and check the Lathe MCP bundle (images, PDF, audio and video, OCR, batch runs, metadata removal). Use when the user installs Lathe, asks what Lathe can do, gets a "lathe." error from a tool, sees a "missing" or "approval_unavailable" result, or wants to turn a module on or off.
license: MIT
source: https://github.com/seayniclabs/lathe
author: Seaynic Labs
---

# Getting started with Lathe

Call `lathe_modules` first. It returns each module with `enabled`, `available` and `missing`. A missing piece comes with the install command for it. Report the missing pieces by name and run the install command the tool gives.

## What each module needs

| Module | On by default | Python extra | System programs | Tools |
|---|---|---|---|---|
| `images` | yes | none (Pillow is always installed) | none | `image_info`, `image_resize`, `image_convert`, `image_optimize`, `image_crop`, `image_thumbnail` |
| `pdf` | yes | `pdf` (pypdf) | ghostscript, for `pdf_to_images` | `pdf_info`, `pdf_extract_text`, `pdf_merge`, `pdf_to_images`, `pdf_split`, `pdf_compress` |
| `media` | yes | none | ffmpeg and ffprobe | `audio_info`, `audio_convert`, `video_info`, `video_thumbnail`, `video_trim`, `video_to_gif` |
| `ocr` | yes | `ocr` (pytesseract) | tesseract | `ocr_image` |
| `batch` | no | none | depends on the operation: ghostscript for `pdf_to_images`, ffmpeg for `audio_convert` | `batch_process` |
| `privacy` | no | `pdf` (pypdf), for PDFs | none | `scrub_metadata` |

`pdf_extract_text` reads scanned pages with OCR when the `ocr` extra, tesseract and ghostscript are all installed.

## Install the pieces

Python extras go in the same command that starts the server. With uv, use `uvx --from "lathe-mcp[pdf,ocr]" lathe`. With pip, use `pip install "lathe-mcp[pdf,ocr]"`.

System programs:

| Program | macOS | Debian or Ubuntu |
|---|---|---|
| ffmpeg (includes ffprobe) | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| tesseract | `brew install tesseract` | `sudo apt install tesseract-ocr` |
| ghostscript | `brew install ghostscript` | `sudo apt install ghostscript` |

## Check the setup

Run `lathe --doctor` in a terminal, using the same command the MCP app runs (`uvx --from "lathe-mcp[pdf,ocr]" lathe --doctor`). It prints `ok` or `FIX` for each piece, names the install command for each FIX, and exits with status 1 when something needs fixing. Run the fixes, then restart the MCP app so it starts the server again.

## Turn a module on or off

Set `LATHE_<MODULE>_ENABLED` to `true` or `false` in the MCP app's `env` block, for example `LATHE_MEDIA_ENABLED=false`. The same setting can go in `~/.config/lathe/config.toml` as `enabled = false` under the module's table. Environment variables win over the file.

The `batch` and `privacy` modules are off after an update. Switch them on only when the user asks for batch runs or metadata removal.

## Set the working folder

Set `LATHE_WORKING_DIR` to the folder that holds the user's files. Every input and output path is relative to it and must stay inside it. Symlinks that point outside are refused. Without this setting, the working folder is the folder the MCP app starts in. Confirm with the user that it is the folder that holds their files.

## Approvals

Only `batch_process` asks the person to approve, and only for a run of two or more files. The MCP client shows the plan once. Claude Code and other clients that support approval prompts show the prompt. If a client cannot show one, the tool returns `approval_unavailable` and names the setting, `LATHE_BATCH_PREAPPROVED=true`. Explain that setting and its effect to the user. Do not set it yourself.

Every other writing tool creates one new file per call and never overwrites one unless the call passes `overwrite=true`. It does not ask.

Every batch request, approval and refusal goes to a local log at `~/.local/state/lathe/approvals.jsonl`. File contents and file names are not logged. Set `LATHE_APPROVAL_LOG` to move the log.

## First checks

1. `health`: returns the version and whether each external program is installed.
2. `image_info` on one image in the working folder: returns width, height and format.
3. `pdf_info` on one PDF, when the `pdf` module is available.

## Errors

Every error reads `lathe.<module>.<code>: <message> Fix: <hint>`. Pass the `Fix:` text to the user as written.
