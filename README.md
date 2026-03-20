# Lathe

File and media processing MCP server built with FastMCP.

Resize, convert, optimize images. Extract text from PDFs. Convert audio and video formats. All through the Model Context Protocol.

## Install

```bash
pip install lathe-mcp
```

For full functionality (ffmpeg, tesseract, ghostscript features):

```bash
pip install "lathe-mcp[full]"
```

## Usage

```bash
lathe
```

Or with the MCP CLI:

```bash
mcp run lathe
```

Set `LATHE_WORKING_DIR` to restrict file access to a specific directory.
