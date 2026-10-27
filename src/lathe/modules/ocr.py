"""OCR: read text from an image with Tesseract (through pytesseract, the ``ocr`` extra)."""

import re
from pathlib import Path
from typing import Annotated

from PIL import Image
from pydantic import BaseModel, Field

from ..errors import LatheError
from . import PYTESSERACT, TESSERACT, Module, Setting, ToolSpec, READ, window

LANG = re.compile(r"^[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*$")


class OcrResult(BaseModel):
    text: str
    lang: str
    total_chars: int
    offset: int
    returned_chars: int
    next_offset: int | None = Field(description="Pass as offset to read the next part. None at the end.")


def _lang(value: str) -> str:
    if not LANG.fullmatch(value) or len(value) > 60:
        raise LatheError("ocr", "bad_input", f"language {value!r} is not a Tesseract language code.",
                         "use codes such as eng, or eng+fra for two languages.")
    return value


def recognize_image(path: Path, lang: str | None) -> str:
    import pytesseract

    chosen = _lang(lang or "eng")
    try:
        with Image.open(path) as img:
            img.load()
            return pytesseract.image_to_string(img, lang=chosen).strip()
    except pytesseract.TesseractNotFoundError:
        raise LatheError("ocr", "unavailable", "the tesseract program was not found.",
                         f"run: {TESSERACT.install}")


class OcrModule(Module):
    name = "ocr"
    summary = "Read the text in an image (Tesseract). Needs the ocr extra and the tesseract program."
    settings: tuple[Setting, ...] = (
        Setting("lang", "Tesseract language code(s), e.g. eng or eng+fra. Default eng.", default="eng"),
    )
    tools = (
        ToolSpec("ocr_image", "Extract the text from an image with OCR. Long text comes in parts: pass next_offset "
                 "as offset to continue. lang overrides LATHE_OCR_LANG.", requires=(PYTESSERACT, TESSERACT),
                 annotations=READ),
    )

    def register(self, mcp, config) -> None:
        self.config = config
        tool = self.tool

        @tool(mcp, "ocr_image")
        def ocr_image(input_path: str, lang: str | None = None,
                      offset: Annotated[int, Field(ge=0)] = 0,
                      max_chars: Annotated[int, Field(ge=1, le=200_000)] = 20_000) -> OcrResult:
            src = self.input_file(input_path)
            chosen = lang or self.setting("lang", "eng")
            text = recognize_image(src, chosen)
            chunk, next_offset = window(text, offset, max_chars)
            return OcrResult(text=chunk, lang=chosen, total_chars=len(text), offset=offset,
                             returned_chars=len(chunk), next_offset=next_offset)
