"""Settings come from environment variables, then an optional TOML file.

Environment variables win. The file is ``$LATHE_CONFIG`` if set, otherwise
``$XDG_CONFIG_HOME/lathe/config.toml`` (``~/.config/lathe/config.toml``).
Core settings are ``LATHE_WORKING_DIR`` and ``LATHE_MAX_FILE_MB`` (the ``[core]``
table in the file). A module setting is ``LATHE_<MODULE>_<KEY>`` and lives in the
``[<module>]`` table. Nothing here assumes a particular MCP client.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Mapping

TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
DEFAULT_MAX_FILE_MB = 500


def config_path(env: Mapping[str, str]) -> Path:
    if env.get("LATHE_CONFIG"):
        return Path(env["LATHE_CONFIG"]).expanduser()
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "lathe" / "config.toml"


def env_name(module: str, key: str) -> str:
    """The environment variable for a setting: LATHE_WORKING_DIR for core, LATHE_OCR_LANG for ocr."""
    if module == "core":
        return f"LATHE_{key.upper()}"
    return f"LATHE_{module.upper()}_{key.upper()}"


class Config:
    def __init__(self, env: Mapping[str, str] | None = None, file_data: dict | None = None):
        self.env = dict(os.environ if env is None else env)
        self.file_error: str | None = None
        if file_data is None:
            path = config_path(self.env)
            file_data = {}
            if path.is_file():
                try:
                    file_data = tomllib.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
                    self.file_error = f"{path} could not be read ({type(e).__name__}); it was ignored."
        self.file = file_data

    def get(self, module: str, key: str, default: str | None = None) -> str | None:
        value = self.env.get(env_name(module, key))
        if value not in (None, ""):
            return value
        value = self.file.get(module, {}).get(key)
        if value not in (None, ""):
            return str(value)
        return default

    def flag(self, module: str, key: str, default: bool) -> bool:
        value = self.get(module, key)
        if value is None:
            return default
        value = value.strip().lower()
        if value in TRUE:
            return True
        if value in FALSE:
            return False
        return default

    def enabled(self, module: str, default: bool) -> bool:
        return self.flag(module, "enabled", default)

    def working_dir(self) -> Path:
        return Path(self.get("core", "working_dir") or os.getcwd()).expanduser().resolve()

    def max_file_mb(self) -> int:
        try:
            value = int(self.get("core", "max_file_mb", str(DEFAULT_MAX_FILE_MB)))
        except ValueError:
            return DEFAULT_MAX_FILE_MB
        return max(1, value)
