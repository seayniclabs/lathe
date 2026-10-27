"""Path checks for every file the server reads or writes.

Relative paths resolve against the working directory, not the process cwd.
Inputs must be files inside the working directory. Outputs must be inside it too,
must not replace an input, and must not replace an existing file unless the
caller passed overwrite=true. Symlinks are resolved before the check, so a link
that points outside the working directory is refused.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable, Iterable

from .errors import LatheError


def _resolve(path: str, root: Path) -> Path:
    if not path or "\x00" in path:
        raise LatheError("core", "bad_path", "the path is empty or contains a NUL byte.",
                         "pass a path to a file inside the working directory.")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _inside(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def resolve_input(path: str, root: Path, max_mb: int) -> Path:
    resolved = _resolve(path, root)
    if not _inside(resolved, root):
        raise LatheError("core", "path_denied", f"{path!r} is outside the working directory {root}.",
                         "use a file inside the working directory, or set LATHE_WORKING_DIR to a folder that contains it.")
    if not resolved.exists():
        raise LatheError("core", "not_found", f"no file at {path!r}.", "check the path, relative to the working directory.")
    if not resolved.is_file():
        raise LatheError("core", "not_a_file", f"{path!r} is not a regular file.", "pass a file, not a folder.")
    size_mb = resolved.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise LatheError("core", "too_large", f"{path!r} is {size_mb:.1f} MB, over the {max_mb} MB limit.",
                         "raise LATHE_MAX_FILE_MB if you really mean to process a file this large.")
    return resolved


def resolve_output(path: str, root: Path, *, overwrite: bool, inputs: Iterable[Path] = ()) -> Path:
    resolved = _resolve(path, root)
    if not _inside(resolved, root):
        raise LatheError("core", "path_denied", f"output {path!r} is outside the working directory {root}.",
                         "write inside the working directory.")
    if resolved in set(inputs):
        raise LatheError("core", "same_path", f"output {path!r} is the input file.",
                         "choose a different output path; Lathe never overwrites its input.")
    if resolved.is_dir():
        raise LatheError("core", "not_a_file", f"output {path!r} is a folder.", "give a file name, such as out.png.")
    if resolved.exists() and not overwrite:
        raise LatheError("core", "exists", f"{path!r} already exists.",
                         "pass overwrite=true to replace it, or choose another name.")
    return resolved


def atomic_write(out: Path, write: Callable[[Path], None]) -> None:
    """Write to a temporary sibling, then move it into place, so a failure never leaves a partial file.

    The temporary name keeps the real suffix so encoders that pick a format by extension still work.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.stem}.{uuid.uuid4().hex[:8]}.tmp{out.suffix}")
    try:
        write(tmp)
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()


def refuse_link(path: str, root: Path) -> None:
    """Refuse a path that is itself a symbolic link. Checked before resolving, which would hide the link."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.is_symlink():
        raise LatheError("core", "path_denied", f"{path!r} is a symbolic link.",
                         "write to a real folder inside the working directory.")


def resolve_dir(path: str, root: Path) -> Path:
    """An output folder inside the working directory. It is created by the caller when needed."""
    resolved = _resolve(path, root)
    if not _inside(resolved, root):
        raise LatheError("core", "path_denied", f"folder {path!r} is outside the working directory {root}.",
                         "write inside the working directory.")
    return resolved
