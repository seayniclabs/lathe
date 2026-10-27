"""`lathe --doctor`: check the working folder, Pillow, and each enabled module's pieces. Prints a fix for each problem.

Makes no network calls and changes nothing. Exit status 0 = ready, 1 = something to fix.
A module that is switched off is listed but not counted, since its pieces are not needed.
"""

from __future__ import annotations

import os
import sys

from . import __version__
from .approvals import log_path
from .config import Config, config_path
from .modules import all_modules


def _checks(config: Config) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    path = config_path(config.env)
    out.append(("config file", True, f"{path} ({'found' if path.is_file() else 'not used'})"))

    wd = config.working_dir()
    writable = wd.is_dir() and os.access(wd, os.W_OK)
    out.append(("working dir", writable,
                str(wd) if writable else f"{wd} is not a writable folder. Fix: set LATHE_WORKING_DIR to a writable folder."))

    try:
        import PIL
        out.append(("images", True, f"Pillow {PIL.__version__} is installed"))
    except ImportError:
        out.append(("images", False, "Pillow is missing. Fix: pip install -U lathe-mcp"))

    for m in all_modules():
        if not config.enabled(m.name, m.default_enabled):
            out.append((m.name, True, "switched off (its pieces are not needed)"))
            continue
        if not m.requirements:
            continue  # images: Pillow is checked above
        missing = [r for r in m.requirements if not r.available()]
        if not missing:
            out.append((m.name, True, "ready"))
            continue
        for r in missing:
            kind = "Python package" if r.kind == "python" else "system program"
            out.append((m.name, False, f"missing {r.name} ({kind}). Fix: {r.install}"))
    out.append(("approval log", True, str(log_path(config.env))))
    return out


def run(config: Config | None = None) -> int:
    config = config or Config()
    results = _checks(config)
    print(f"lathe-mcp {__version__} doctor")
    for name, ok, msg in results:
        print(f"  {'ok ' if ok else 'FIX'}  {name:<13} {msg}")
    bad = sum(1 for _, ok, _ in results if not ok)
    print("ready" if not bad else f"{bad} thing(s) to fix")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run())
