"""License validation for Lathe MCP server.

Checks for a valid your organization license key to unlock paid tools.
License can be provided via:
  1. License file at ~/.seayniclabs/license.json
  2. LATHE_LICENSE_KEY environment variable

License JSON format:
    {"key": "SL-XXXX-XXXX", "product": "lathe-mcp", "email": "...", "issued": "..."}
"""

import json
import os
from pathlib import Path

LICENSE_FILE = Path.home() / ".seayniclabs" / "license.json"
LICENSE_ENV_VAR = "LATHE_LICENSE_KEY"


def _read_license_file() -> str | None:
    """Read the license key from the license file, or None if unavailable."""
    try:
        if LICENSE_FILE.exists():
            data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("key")
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return None


def _read_license_env() -> str | None:
    """Read the license key from the environment variable, or None."""
    return os.environ.get(LICENSE_ENV_VAR) or None


def _validate_key(key: str | None) -> bool:
    """Check that a key exists and has the expected prefix."""
    return isinstance(key, str) and key.startswith("SL-") and len(key) >= 7


def is_licensed() -> bool:
    """Return True if a valid your organization license is present."""
    # Check env var first (takes precedence — easier for CI/Docker)
    env_key = _read_license_env()
    if _validate_key(env_key):
        return True

    # Fall back to license file
    file_key = _read_license_file()
    return _validate_key(file_key)
