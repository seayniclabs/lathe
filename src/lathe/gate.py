"""The approval gate for tools that write files.

Gauge's pattern. Only batch_process uses this gate, and only for a run of two or more
files. The run is approved in one of three ways, in this order:

1. The batch module is pre-approved in settings (``LATHE_BATCH_PREAPPROVED=true``).
2. The person is asked through the MCP client (elicitation) and says yes.
3. The client cannot ask, so the run is refused with ``approval_unavailable``.

The model's own arguments never count as approval. Every step is written to the
local approval log.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from . import approvals
from .errors import LatheError


class Approval(BaseModel):
    approve: bool = Field(description="Let Lathe run this now?")


def can_ask(ctx) -> bool:
    try:
        caps = ctx.session.client_params.capabilities  # type: ignore[union-attr]
    except (ValueError, AttributeError):
        return False
    return bool(caps and caps.elicitation)


async def approve(ctx, config, module: str, tool: str, summary: str, details: dict) -> str:
    """Return "settings" or "person". Raises a lathe error when declined or when nobody can approve."""
    if config.flag(module, "preapproved", False):
        approvals.record(config.env, tool, "approved", "settings", details)
        return "settings"
    if not can_ask(ctx):
        approvals.record(config.env, tool, "refused", None, details)
        raise LatheError(module, "approval_unavailable",
                         "this MCP client cannot ask you to approve this run, and the module is not pre-approved.",
                         f"set LATHE_{module.upper()}_PREAPPROVED=true to let Lathe run it without asking, "
                         "or use a client that supports approval prompts.")
    approvals.record(config.env, tool, "requested", None, details)
    answer = await ctx.elicit(summary, Approval)
    if answer.action != "accept" or not answer.data.approve:
        approvals.record(config.env, tool, "declined", "person", details)
        raise LatheError(module, "declined", "the person declined. Nothing was written.",
                         "run the tool again only if the person asks for it.")
    approvals.record(config.env, tool, "approved", "person", details)
    return "person"
