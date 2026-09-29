# mcp_client.py
# The orchestrator's side of the MCP boundary: one function that calls a tool
# on one sandboxed server and returns its parsed result.
#
# It takes a server name and a tool name. There is no parameter for a header,
# a token or a key, and that is deliberate -- the researcher's Anthropic key
# stays in this process and never reaches a container that opens untrusted
# files. See INTEGRATION_CONTRACT.md section 2.

from __future__ import annotations

import json
from typing import Any

from mcp import Client
from mcp.types import TextContent

from common.servers import mcp_url
from common.tooling import TOOL_TIMEOUT_SECONDS

# Longer than the server's own tool timeout, so a tool that is killed server
# side reports a timeout rather than the client giving up first and leaving
# the sandbox still working. The client deadline is the backstop for a server
# that stops answering altogether, which its own timeout cannot cover.
CLIENT_TIMEOUT_SECONDS = TOOL_TIMEOUT_SECONDS * 2


class ToolCallFailed(RuntimeError):
    """A server reported an error result for a tool call."""


async def call_tool(
    server: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
    timeout: float = CLIENT_TIMEOUT_SECONDS,
) -> Any:
    """Call one tool on one server and return its result."""
    async with Client(mcp_url(server), read_timeout_seconds=timeout) as client:
        result = await client.call_tool(tool, arguments or {})

    if result.is_error:
        raise ToolCallFailed(f"{server}.{tool} failed: {_text_of(result.content)}")

    # Structured output when the server provides it. The R server has no
    # structured-output support, so it returns JSON text; parsing the text is
    # the path that works for both, and both are checked here rather than
    # branching on which server answered.
    if result.structured_content is not None:
        return result.structured_content
    return _parse(_text_of(result.content))


async def list_tools(server: str, timeout: float = CLIENT_TIMEOUT_SECONDS) -> list[str]:
    """Names of the tools a server exposes."""
    async with Client(mcp_url(server), read_timeout_seconds=timeout) as client:
        listing = await client.list_tools()
    return [tool.name for tool in listing.tools]


def _text_of(content: list[Any]) -> str:
    return "\n".join(block.text for block in content if isinstance(block, TextContent))


def _parse(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # A tool that answers in prose is not an error; only a tool that
        # claims to answer in JSON and does not would be, and that shows up
        # as a schema failure where the result is used.
        return text
