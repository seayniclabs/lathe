"""Module contract and registry.

A module is one family of operations (images, pdf, media, ocr). It declares its
settings and the tools it provides, and registers them on the shared server.
Adding a module means adding a file here and listing it in ``all_modules()``.
Modules added after 0.3 must set ``default_enabled = False`` so an update never
turns on something the user did not choose.

A module whose Python extra or system binary is missing still starts and still
lists its tools. Calling one of those tools returns ``lathe.<module>.unavailable``
with the install command for the missing piece.

Tools that write files ask for approval first (see ``lathe.gate``). Every module
that has such a tool carries the ``preapproved`` setting, so a person can allow
writes in settings instead of answering a prompt each time.
"""

from __future__ import annotations

import functools
import importlib.util
import inspect
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..config import Config
from ..errors import LatheError
from ..paths import resolve_input, resolve_output

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)

# Patched in tests to simulate a missing dependency.
_which: Callable[[str], str | None] = shutil.which


def _has_python_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _install(brew: str, apt: str) -> str:
    if sys.platform == "darwin":
        return brew
    if sys.platform.startswith("linux"):
        return apt
    return f"install {brew.split()[-1]} and put it on PATH"


@dataclass(frozen=True)
class Requirement:
    kind: str  # "python" (an importable module) or "binary" (an executable on PATH)
    name: str
    install: str  # the command that fixes it, for this platform

    def available(self) -> bool:
        if self.kind == "python":
            return _has_python_module(self.name)
        return _which(self.name) is not None


PYPDF = Requirement("python", "pypdf", 'pip install "lathe-mcp[pdf]"')
PYTESSERACT = Requirement("python", "pytesseract", 'pip install "lathe-mcp[ocr]"')
TESSERACT = Requirement("binary", "tesseract", _install("brew install tesseract", "apt install tesseract-ocr"))
GHOSTSCRIPT = Requirement("binary", "gs", _install("brew install ghostscript", "apt install ghostscript"))
FFMPEG = Requirement("binary", "ffmpeg", _install("brew install ffmpeg", "apt install ffmpeg"))
FFPROBE = Requirement("binary", "ffprobe", _install("brew install ffmpeg", "apt install ffmpeg"))


@dataclass(frozen=True)
class Setting:
    key: str
    help: str
    default: str | None = None
    secret: bool = False

    def env_var(self, module: str) -> str:
        from ..config import env_name
        return env_name(module, self.key)


PREAPPROVED = Setting("preapproved", "true lets Lathe write files without asking. Default false: the person "
                      "is asked to approve each run.", default="false")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    requires: tuple[Requirement, ...] = ()
    annotations: ToolAnnotations = field(default_factory=lambda: READ)
    gated: bool = False  # True: the run asks the person to approve it (see lathe.gate)


def unavailable(module: str, missing: list[Requirement]) -> LatheError:
    names = ", ".join(f"{r.name} ({'Python package' if r.kind == 'python' else 'system program'})" for r in missing)
    fix = " && ".join(dict.fromkeys(r.install for r in missing))
    return LatheError(module, "unavailable", f"missing {names}.", f"run: {fix}")


def relpath(path: Path, root: Path) -> str:
    """A path for people to read: relative to the working directory when it is inside it."""
    try:
        return path.relative_to(root).as_posix() or "."
    except ValueError:
        return str(path)


def window(text: str, offset: int, max_chars: int) -> tuple[str, int | None]:
    """A slice of text for paging, and the offset of the next slice (None at the end)."""
    chunk = text[offset:offset + max_chars]
    end = offset + len(chunk)
    return chunk, (end if end < len(text) else None)


def parse_pages(spec: str, total: int) -> list[int]:
    """Parse "3", or "2-5" (1-indexed, inclusive) into 0-indexed page numbers."""
    spec = spec.strip()
    try:
        if "-" in spec:
            first_s, last_s = spec.split("-", 1)
            first, last = int(first_s), int(last_s)
        else:
            first = last = int(spec)
    except ValueError:
        raise LatheError("pdf", "bad_input", f"page range {spec!r} is not a number or a range like 2-5.",
                         "use pages like \"3\" or \"2-5\".")
    if first < 1 or last < first:
        raise LatheError("pdf", "bad_input", f"page range {spec!r} is not valid.", "start at 1 and end at or after the start.")
    if first > total:
        raise LatheError("pdf", "bad_input", f"page range {spec!r} is outside 1-{total}.", "use pages within the document.")
    return list(range(first - 1, min(last, total)))


class Module:
    name: str = ""
    summary: str = ""
    settings: tuple[Setting, ...] = ()
    tools: tuple[ToolSpec, ...] = ()
    default_enabled: bool = True

    def __init__(self) -> None:
        self.config: Config | None = None

    @property
    def requirements(self) -> list[Requirement]:
        seen: dict[str, Requirement] = {}
        for spec in self.tools:
            for r in spec.requires:
                seen.setdefault(f"{r.kind}:{r.name}", r)
        return list(seen.values())

    def spec(self, name: str) -> ToolSpec:
        return next(t for t in self.tools if t.name == name)

    def register(self, mcp: FastMCP, config: Config) -> None:
        raise NotImplementedError

    def tool(self, mcp: FastMCP, name: str):
        """Register a function as the named tool. Checks dependencies first and wraps other failures as lathe errors.

        Coroutine functions (the tools that ask for approval) are wrapped as coroutines.
        """
        spec = self.spec(name)

        def wrap(e: Exception) -> LatheError:
            return LatheError(self.name, "failed", f"{type(e).__name__}: {str(e)[:300]}",
                              "check the input file, then try again.")

        def decorate(fn):
            if inspect.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def guarded(*args, **kwargs):
                    missing = [r for r in spec.requires if not r.available()]
                    if missing:
                        raise unavailable(self.name, missing)
                    try:
                        return await fn(*args, **kwargs)
                    except LatheError:
                        raise
                    except Exception as e:
                        raise wrap(e) from e
            else:
                @functools.wraps(fn)
                def guarded(*args, **kwargs):
                    missing = [r for r in spec.requires if not r.available()]
                    if missing:
                        raise unavailable(self.name, missing)
                    try:
                        return fn(*args, **kwargs)
                    except LatheError:
                        raise
                    except Exception as e:
                        raise wrap(e) from e

            mcp.tool(name=spec.name, description=spec.description, annotations=spec.annotations)(guarded)
            return fn

        return decorate

    def need(self, *reqs: Requirement) -> None:
        """Raise the unavailable error for any of these pieces that is missing (for checks inside a tool)."""
        missing = [r for r in reqs if not r.available()]
        if missing:
            raise unavailable(self.name, missing)

    # Shared path handling. Every tool goes through these.
    def input_file(self, path: str):
        cfg = self.config
        return resolve_input(path, cfg.working_dir(), cfg.max_file_mb())

    def output_file(self, path: str, overwrite: bool, inputs=()):
        return resolve_output(path, self.config.working_dir(), overwrite=overwrite, inputs=inputs)

    def setting(self, key: str, default: str | None = None) -> str | None:
        return self.config.get(self.name, key, default)


def all_modules() -> list[Module]:
    from .batch import BatchModule
    from .images import ImagesModule
    from .media import MediaModule
    from .ocr import OcrModule
    from .pdf import PdfModule
    from .privacy import PrivacyModule

    return [ImagesModule(), PdfModule(), MediaModule(), OcrModule(), BatchModule(), PrivacyModule()]
