"""batch_process: one operation over every matching file in a folder, in one call.

A dry run (the default) returns the plan and writes nothing: which files match, where
each output goes, and which are skipped or rejected and why. A real run of more than
one file asks the person to approve the plan through the client, unless the batch
module is pre-approved (``LATHE_BATCH_PREAPPROVED=true``). Inputs are never
overwritten. An existing output is skipped unless the call passes overwrite=true.

Note: no ``from __future__ import annotations`` here (see images.py).
"""

from pathlib import Path
from typing import Annotated, Literal

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..errors import LatheError
from ..gate import approve
from ..paths import resolve_dir, resolve_input
from . import (FFMPEG, GHOSTSCRIPT, PREAPPROVED, PYPDF, Module, Requirement, Setting, ToolSpec, WRITE, relpath)
from . import images as img
from . import media as media_mod
from . import pdf as pdf_mod

OPERATIONS = ("image_resize", "image_convert", "image_optimize", "image_thumbnail", "pdf_to_images", "audio_convert")
REQUIRES = {"pdf_to_images": (PYPDF, GHOSTSCRIPT), "audio_convert": (FFMPEG,)}
DEFAULT_MAX_FILES = 50
CAP_MAX_FILES = 500
APPROVAL_LIST = 10
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp"}
CONVERT_EXT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "AVIF": ".avif", "BMP": ".bmp"}
AUDIO_EXT = {"mp3": ".mp3", "wav": ".wav", "flac": ".flac", "aac": ".aac", "ogg": ".ogg"}


class BatchItem(BaseModel):
    input_path: str
    output_path: str | None = Field(description="Relative to the working directory. For pdf_to_images, a folder.")
    status: str = Field(description="planned (dry run), done, failed, skipped (output exists) or rejected (input refused).")
    reason: str | None = None
    output_bytes: int | None = None


class BatchResult(BaseModel):
    operation: str
    dry_run: bool
    folder: str
    output_folder: str
    pattern: str
    matched: int = Field(description="Files the pattern matched, before the max_files cap.")
    truncated: bool = Field(description="True when more files matched than max_files allowed.")
    planned: int
    done: int
    failed: int
    skipped: int
    rejected: int
    approved_by: str | None = Field(None, description="settings or person. None for a dry run or a single file.")
    note: str | None = None
    items: list[BatchItem]


def _options(op: str, width, height, percentage, format, quality, size, dpi) -> dict:
    if op == "image_resize":
        if not (width or height or percentage):
            raise LatheError("batch", "bad_input", "image_resize needs width, height or percentage.",
                             "pass one of them.")
        return {"width": width, "height": height, "percentage": percentage}
    if op == "image_convert":
        fmt = img.FORMAT_BY_NAME.get((format or "").strip().lower())
        if fmt is None:
            raise LatheError("batch", "bad_input", f"image_convert needs a format: {format!r} is not one.",
                             "use png, jpeg, webp, avif or bmp.")
        return {"format": format.strip().lower(), "fmt": fmt}
    if op == "image_optimize":
        return {"quality": quality or 80}
    if op == "image_thumbnail":
        return {"size": size or 128}
    if op == "pdf_to_images":
        fmt = (format or "png").strip().lower()
        if fmt not in ("png", "jpeg"):
            raise LatheError("batch", "bad_input", f"pdf_to_images format {format!r} is not png or jpeg.",
                             "use png or jpeg.")
        return {"format": fmt, "dpi": dpi or 150}
    if op == "audio_convert":
        fmt = (format or "").strip().lower()
        if fmt not in AUDIO_EXT:
            raise LatheError("batch", "bad_input", f"audio_convert needs a format: {format!r} is not one.",
                             "use mp3, wav, flac, aac or ogg.")
        return {"format": fmt}
    raise LatheError("batch", "bad_input", f"unknown operation {op!r}.", "use one of: " + ", ".join(OPERATIONS))


def _output_name(op: str, src: Path, opts: dict) -> str:
    suffix = src.suffix.lower()
    if op == "pdf_to_images":
        return src.stem  # a folder per PDF
    if op == "image_convert":
        return src.stem + CONVERT_EXT[opts["fmt"]]
    if op == "image_optimize":
        ext = suffix if suffix in {".png", ".webp", ".jpg", ".jpeg"} else ".jpg"
    elif op in ("image_resize", "image_thumbnail"):
        ext = suffix if suffix in IMAGE_SUFFIXES else ".png"
    else:  # audio_convert
        ext = AUDIO_EXT[opts["format"]]
    return src.stem + ext


def _matches(folder: Path, pattern: str) -> list[Path]:
    if not pattern or "\x00" in pattern or pattern.startswith(("/", "\\")) or ".." in Path(pattern).parts:
        raise LatheError("batch", "bad_input", f"pattern {pattern!r} must be a relative glob inside the folder.",
                         "use a pattern such as *.jpg or **/*.png, with no leading slash and no '..'.")
    try:
        return sorted(p for p in folder.glob(pattern) if p.is_file())
    except (ValueError, NotImplementedError):
        raise LatheError("batch", "bad_input", f"pattern {pattern!r} is not a valid glob.",
                         "use a pattern such as *.jpg or **/*.png.")


def _run_one(op: str, src: Path, out: Path, opts: dict, overwrite: bool) -> dict:
    if op == "image_resize":
        return img.op_resize(src, out, opts["width"], opts["height"], opts["percentage"])
    if op == "image_convert":
        return img.op_convert(src, out, opts["format"])
    if op == "image_optimize":
        return img.op_optimize(src, out, opts["quality"], True)
    if op == "image_thumbnail":
        return img.op_thumbnail(src, out, opts["size"])
    if op == "pdf_to_images":
        total = len(pdf_mod._reader(src).pages)
        if total == 0:
            raise LatheError("pdf", "bad_input", f"{src.name} has no pages.", "skip it or fix the file.")
        return pdf_mod.op_pdf_to_images(src, out, list(range(total)), opts["format"], opts["dpi"], overwrite)
    return media_mod.op_audio_convert(src, out, opts["format"])


class BatchModule(Module):
    name = "batch"
    summary = ("Run one operation (resize, convert, optimize, thumbnail, PDF to images, audio convert) over every "
               "matching file in a folder. Dry run first; asks you to approve a multi-file run.")
    settings: tuple[Setting, ...] = (PREAPPROVED,)
    default_enabled = False
    tools = (
        ToolSpec("batch_process", "Apply one operation to every file matching a glob in a folder. dry_run=true (the "
                 "default) returns the plan and writes nothing. A real run of more than one file asks the person to "
                 "approve the plan. Inputs are never overwritten; existing outputs are skipped unless overwrite=true.",
                 annotations=WRITE, gated=True),
    )

    @property
    def requirements(self) -> list[Requirement]:
        seen: dict[str, Requirement] = {}
        for reqs in REQUIRES.values():
            for r in reqs:
                seen.setdefault(f"{r.kind}:{r.name}", r)
        return list(seen.values())

    def register(self, mcp, config) -> None:
        self.config = config
        tool = self.tool

        @tool(mcp, "batch_process")
        async def batch_process(
            ctx: Context,
            folder: str,
            operation: Literal["image_resize", "image_convert", "image_optimize", "image_thumbnail",
                               "pdf_to_images", "audio_convert"],
            output_folder: str,
            pattern: str = "*",
            dry_run: bool = True,
            max_files: Annotated[int, Field(ge=1, le=CAP_MAX_FILES)] = DEFAULT_MAX_FILES,
            overwrite: bool = False,
            width: Annotated[int | None, Field(ge=1, le=img.MAX_PIXELS)] = None,
            height: Annotated[int | None, Field(ge=1, le=img.MAX_PIXELS)] = None,
            percentage: Annotated[float | None, Field(gt=0, le=1000)] = None,
            format: str | None = None,
            quality: Annotated[int | None, Field(ge=1, le=100)] = None,
            size: Annotated[int | None, Field(ge=1, le=4096)] = None,
            dpi: Annotated[int | None, Field(ge=72, le=600)] = None,
        ) -> BatchResult:
            root = self.config.working_dir()
            src_dir = resolve_dir(folder, root)
            if not src_dir.is_dir():
                raise LatheError("batch", "not_found", f"no folder at {folder!r}.",
                                 "pass a folder inside the working directory.")
            out_dir = resolve_dir(output_folder, root)
            if out_dir == src_dir:
                raise LatheError("batch", "same_path", "output_folder is the input folder.",
                                 "choose another output folder. Lathe never writes over its inputs.")
            if out_dir.exists() and not out_dir.is_dir():
                raise LatheError("core", "not_a_file", f"{output_folder!r} is a file, not a folder.",
                                 "give a folder name.")
            opts = _options(operation, width, height, percentage, format, quality, size, dpi)
            self.need(*REQUIRES.get(operation, ()))

            found = _matches(src_dir, pattern)
            matched = len(found)
            found = found[:max_files]
            max_mb = self.config.max_file_mb()
            plan, taken, planned = [], set(), []
            for path in found:
                rel_in = relpath(path, root)
                try:
                    src = resolve_input(str(path), root, max_mb)
                except LatheError as e:
                    plan.append({"input_path": rel_in, "output_path": None, "status": "rejected", "reason": str(e)})
                    continue
                name = _output_name(operation, src, opts)
                out = out_dir / name
                rel_out = relpath(out, root)
                if out == src:
                    plan.append({"input_path": rel_in, "output_path": rel_out, "status": "rejected",
                                 "reason": "the output would replace its input."})
                elif name in taken:
                    plan.append({"input_path": rel_in, "output_path": rel_out, "status": "rejected",
                                 "reason": f"another input in this run also writes {name}."})
                elif out.exists() and not overwrite:
                    plan.append({"input_path": rel_in, "output_path": rel_out, "status": "skipped",
                                 "reason": "the output already exists; pass overwrite=true to replace it."})
                else:
                    taken.add(name)
                    plan.append({"input_path": rel_in, "output_path": rel_out, "status": "planned", "reason": None})
                    planned.append((plan[-1], src, out))

            folder_rel, out_rel = relpath(src_dir, root), relpath(out_dir, root)

            def counts(items: list[dict]) -> dict:
                return {k: sum(1 for i in items if i["status"] == k) for k in ("planned", "skipped", "rejected")}

            if dry_run or not planned:
                note = None
                if not planned:
                    note = "Nothing to run: no file matched, or every match was skipped or rejected."
                elif dry_run:
                    note = (f"Dry run: nothing was written. Call again with dry_run=false to run {len(planned)} file(s)."
                            + (" A real run of more than one file asks the person to approve it." if len(planned) > 1 else ""))
                c = counts(plan)
                return BatchResult(operation=operation, dry_run=dry_run, folder=folder_rel, output_folder=out_rel,
                                   pattern=pattern, matched=matched, truncated=matched > max_files,
                                   planned=c["planned"], done=0, failed=0, skipped=c["skipped"], rejected=c["rejected"],
                                   note=note, items=[BatchItem(**i) for i in plan])

            names = [p[0]["input_path"] for p in planned]
            shown = ", ".join(names[:APPROVAL_LIST]) + (f", and {len(names) - APPROVAL_LIST} more" if len(names) > APPROVAL_LIST else "")
            options = ", ".join(f"{k}={v}" for k, v in opts.items() if k != "fmt" and v is not None)
            summary = (f"Run {operation} on {len(planned)} file(s) from {folder_rel} and write them to {out_rel}"
                       f"{' (' + options + ')' if options else ''}? Files: {shown}. "
                       "Existing outputs are skipped unless overwrite is set.")
            approved = None
            if len(planned) > 1:
                approved = await approve(ctx, self.config, self.name, "batch_process", summary,
                                         {"operation": operation, "folder": folder_rel, "output_folder": out_rel,
                                          "pattern": pattern, "files": len(planned)})
            out_dir.mkdir(parents=True, exist_ok=True)
            done_items: dict[str, BatchItem] = {}
            for entry, src, out in planned:
                try:
                    r = _run_one(operation, src, out, opts, overwrite)
                    done_items[entry["input_path"]] = BatchItem(
                        input_path=entry["input_path"], output_path=entry["output_path"], status="done",
                        output_bytes=r.get("output_bytes"))
                except LatheError as e:
                    done_items[entry["input_path"]] = BatchItem(
                        input_path=entry["input_path"], output_path=entry["output_path"], status="failed", reason=str(e))
                except Exception as e:  # one bad file must not stop the rest of the batch
                    done_items[entry["input_path"]] = BatchItem(
                        input_path=entry["input_path"], output_path=entry["output_path"], status="failed",
                        reason=f"{type(e).__name__}: {str(e)[:200]}")
            items = [done_items[i["input_path"]] if i["input_path"] in done_items else BatchItem(**i) for i in plan]
            return BatchResult(
                operation=operation, dry_run=False, folder=folder_rel, output_folder=out_rel, pattern=pattern,
                matched=matched, truncated=matched > max_files,
                planned=0, done=sum(1 for i in items if i.status == "done"),
                failed=sum(1 for i in items if i.status == "failed"),
                skipped=sum(1 for i in items if i.status == "skipped"),
                rejected=sum(1 for i in items if i.status == "rejected"),
                approved_by=approved, items=items,
                note=("Run finished. Failed files are listed with their reason." if any(i.status == "failed" for i in items) else None),
            )
