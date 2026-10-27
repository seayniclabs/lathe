"""Local approval log: one JSON line per approval asked, granted, declined or refused.

Written to $LATHE_APPROVAL_LOG, or $XDG_STATE_HOME/lathe/approvals.jsonl
(~/.local/state/lathe/approvals.jsonl). It never leaves the machine. File contents
are never logged. Only what a person approves is: the operation, the folders and
the number of files, plus the file names of a single-file run.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Mapping


def log_path(env: Mapping[str, str]) -> Path:
    if env.get("LATHE_APPROVAL_LOG"):
        return Path(env["LATHE_APPROVAL_LOG"]).expanduser()
    base = env.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "lathe" / "approvals.jsonl"


def record(env: Mapping[str, str], tool: str, decision: str, by: str | None, details: dict) -> None:
    """decision: requested | approved | declined | refused. Never raises: logging must not break a run."""
    try:
        path = log_path(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": tool,
                "decision": decision, "approved_by": by, **details}
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)
    except OSError:
        pass
