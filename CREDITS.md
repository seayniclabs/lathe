# Credits

Lathe is made by [Seaynic Labs](https://seayniclabs.com) and released under the MIT license.

## Skills

All skills in `skills/` were written for Lathe by Seaynic Labs and are MIT licensed. None is copied from another project, so there are no third-party skill files to attribute. The `pdf` skill was adapted from Seaynic Labs' own PDF command, and `pdf-forms` from its own fillable-form notes; both were rewritten for a general setup.

## Libraries

Lathe depends on these packages at run time. Each keeps its own license; the versions are the ones in `uv.lock`.

| Package | Used for | License |
|---|---|---|
| mcp (Model Context Protocol SDK) | the server | MIT |
| Pillow | images | MIT-CMU (HPND) |
| pydantic | tool input and output schemas | MIT |
| pypdf (`pdf` extra) | PDF reading, merging, splitting, compressing | BSD-3-Clause |
| pytesseract (`ocr` extra) | Tesseract wrapper | Apache-2.0 |

Lathe calls these programs but does not ship them: ffmpeg and ffprobe (LGPL or GPL, depending on build), Tesseract (Apache-2.0), and Ghostscript (AGPL, or a commercial license). Install them with your system package manager; see `lathe --doctor`.
