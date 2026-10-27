---
name: web-image-prep
description: Prepare a folder of photos or screenshots for a website or post: remove GPS and camera metadata, resize, and optimize each file in one batch run. Use when the user wants to shrink, convert or clean photos before uploading them, or asks to remove location data from a picture.
license: MIT
source: https://github.com/seayniclabs/lathe
author: Seaynic Labs
---

# Prepare photos for the web

Two tools do the work: `scrub_metadata` (privacy module) for one file at a time, and `batch_process` (batch module) for a folder. Both modules are off after an update. Turn them on with `LATHE_PRIVACY_ENABLED=true` and `LATHE_BATCH_ENABLED=true` in the MCP app's `env` block, restart the app, then call `lathe_modules` to confirm both are on.

## Steps

1. Inspect one photo first. Call `scrub_metadata` with `mode="inspect"` on it. It returns `gps_present` and the list of fields. Tell the user whether the photo has GPS data and which camera fields it holds. Do not repeat the coordinates in chat unless the user asks for them.
2. Dry-run the folder. Call `batch_process` with `dry_run` left at its default of true, `operation="image_optimize"`, `folder` and `output_folder` inside the working folder, and `quality=80`. Read the plan: how many files are planned, how many are skipped because the output exists, and how many are rejected, with the reason for each rejected file.
3. Run it. Call the same tool with `dry_run=false`. A run of two or more files asks the person once to approve the whole plan in the MCP client. A declined run writes nothing. A single file runs without a prompt.
4. Check the output. Call `scrub_metadata` with `mode="inspect"` on one file in the output folder. `gps_present` must be false.
5. Report the result: files done, files failed (with each reason), and the output folder.

## Choosing the operation

| Need | Operation | Notes |
|---|---|---|
| Smaller files, same format, metadata removed | `image_optimize` | Strips metadata unless `strip_metadata=false`. JPEG, PNG and WebP keep their extension. |
| A fixed width for web pages | `image_resize` with `width=1600` | Keeps the aspect ratio. Writes pixels only, so EXIF and GPS are not copied. |
| Modern format | `image_convert` with `format="webp"` | WebP output uses quality 85. |
| Small previews | `image_thumbnail` with `size=400` | Fits inside a 400 x 400 square. |

Run `image_resize` first when the photos are very large, then `image_optimize` on its output folder. Each run of two or more files asks once for its approval.

## Rules

- Never write over the originals: use a new `output_folder`. `batch_process` refuses an output folder that is the input folder.
- An output that already exists is skipped. Set `overwrite=true` only when the user asks to replace the earlier files.
- `max_files` defaults to 50 and is capped at 500. When `truncated` is true, say how many files were left out, and run the rest in a second call with a narrower `pattern`.
- Metadata removal is a privacy step: never report that a photo is clean without an inspect call on its output.
