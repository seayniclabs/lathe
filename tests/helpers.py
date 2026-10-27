"""Shared helpers for the 0.4 tests: a server per environment, and a real client that answers approval prompts."""

import asyncio
import re

from lathe.config import Config
from lathe.server import build_server

ERROR = re.compile(r"lathe\.[a-z_]+\.[a-z_]+: ")


def server(box, **env):
    return build_server(Config(env={"LATHE_WORKING_DIR": str(box), **env}, file_data={}))


def call(mcp, name, **args):
    """Call a tool directly (no client, so no approval prompt can be answered)."""
    _, structured = asyncio.run(mcp.call_tool(name, args))
    return structured


def call_with_client(mcp, name, args, answer):
    """Call a tool through a real MCP client. answer: True / False (the person's choice) or None (decline)."""
    from mcp.shared.memory import create_connected_server_and_client_session
    from mcp.types import ElicitResult

    asked = []

    async def on_elicit(context, params):
        asked.append(params.message)
        if answer is None:
            return ElicitResult(action="decline")
        return ElicitResult(action="accept", content={"approve": answer})

    async def run():
        async with create_connected_server_and_client_session(mcp, elicitation_callback=on_elicit) as client:
            result = await client.call_tool(name, args)
            return result.structuredContent, result.isError, (result.content[0].text if result.isError else "")

    structured, is_error, text = asyncio.run(run())
    return structured, is_error, text, asked


def error_code(text_or_exc) -> str:
    match = re.search(r"lathe\.[a-z_]+\.([a-z_]+):", str(text_or_exc))
    return match.group(1) if match else ""
