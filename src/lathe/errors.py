"""One error shape for every module, so scripts can rely on it.

Every failure a tool reports reads: ``lathe.<module>.<code>: <message> Fix: <hint>``.
Paths and configuration use the module name ``core``.
"""

from mcp.server.fastmcp.exceptions import ToolError


class LatheError(ToolError):
    def __init__(self, module: str, code: str, message: str, hint: str = ""):
        self.module = module
        self.code = code
        text = f"lathe.{module}.{code}: {message}"
        if hint:
            text += f" Fix: {hint}"
        super().__init__(text)
