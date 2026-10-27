---
name: pdf
description: Convert a Markdown file to a PDF with Chrome or Chromium in headless mode. Use when the user asks to turn a Markdown note, report or spec into a PDF and Chrome or Chromium is installed. Lathe's own PDF tools do not render Markdown.
license: MIT
source: https://github.com/seayniclabs/lathe
author: Seaynic Labs
---

# Markdown to PDF with Chrome

This skill needs Google Chrome or Chromium on the machine, plus Python 3. It does not use a Lathe tool. Lathe's PDF tools merge, split, compress, read and render existing PDFs, but they do not render Markdown.

If Chrome or Chromium is not installed, say so plainly and stop. Name the install step: install Google Chrome from google.com/chrome on macOS, or `sudo apt install chromium` on Debian and Ubuntu.

## Steps

1. Get the input path. If the user gave none, ask which file to convert.
2. Pick the output path. Put the PDF beside the Markdown file, with the same name and a `.pdf` extension, unless the user names a folder.
3. Work in a new temporary folder for the HTML and any images. Never write into the source folder except for the PDF.
4. Remove YAML frontmatter: delete the block between the first two `---` lines when the file starts with one.
5. Turn Obsidian links into plain text: `[[target|label]]` becomes `label`, and `[[target]]` becomes `target`.
6. Render each ```` ```mermaid ```` block to PNG with `npx --yes @mermaid-js/mermaid-cli -i <block>.mmd -o <block>.png -b white -w 1200 --scale 2`. Replace the block with an `<img>` tag that points at the PNG. If `npx` is missing, leave the block as a code block and tell the user.
7. Convert the Markdown to HTML with the Python `markdown` package and the `tables`, `fenced_code` and `toc` extensions. Install it in a virtual environment in the temporary folder: `python3 -m venv venv && venv/bin/pip install markdown`.
8. Wrap the HTML in a page with a `<meta charset="utf-8">` tag and a `<style>` block for body text, headings, tables and code.
9. Print the page to PDF with Chrome in headless mode, using absolute paths:

   macOS:
   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
     --print-to-pdf="/absolute/path/out.pdf" "file:///absolute/path/page.html"
   ```

   Linux, with `chromium` or `google-chrome` on the PATH:
   ```bash
   chromium --headless --disable-gpu --print-to-pdf="/absolute/path/out.pdf" "file:///absolute/path/page.html"
   ```

10. Check that the PDF exists and is not empty. Report its absolute path and size in KB.

## Rules

- Use absolute paths in every command. Chrome needs `file://` URLs with absolute paths.
- Do not open the PDF after writing it. Report the path and let the user open it.
- Never change the Markdown file.
- Mermaid diagrams are always drawn as images. Never leave placeholder text in the PDF.
