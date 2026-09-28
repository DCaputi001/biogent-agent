# mcp_app.py
# Builds and runs the MCP server every Python sandbox exposes, so the servers
# themselves differ only by the tools they register.
#
# Two things here are load-bearing rather than boilerplate: the Host allowlist,
# without which the SDK rejects every request the orchestrator makes, and the
# /healthz route, without which the container healthcheck cannot tell a healthy
# server from a hung one.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import uvicorn
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from common.health import BIND_HOST, health_payload
from common.servers import HEALTH_PATH, SERVER_PORT, allowed_hosts
from common.tooling import (
    TOOL_TIMEOUT_SECONDS,
    ToolExecutionError,
    ToolTimeout,
    run_with_timeout,
)

# Called with the server so a component can register its tools on it.
ToolRegistrar = Callable[[MCPServer], None]


def run_tool(
    func: Callable[..., Any],
    *args: Any,
    seconds: float = TOOL_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> Any:
    """Run a tool body under the wall-clock limit, reporting failures to the client.

    Every tool goes through this rather than calling run_with_timeout directly.
    The SDK masks an unanticipated exception behind "Error executing tool
    <name>" and logs the traceback server side, which is the right default for
    a crash but wrong for a timeout: the caller needs to know it ran out of
    time, and in a sandbox the server log is the harder place to look.
    """
    try:
        return run_with_timeout(func, *args, seconds=seconds, **kwargs)
    except (ToolTimeout, ToolExecutionError) as error:
        raise ToolError(str(error)) from error


def build_app(component: str, register_tools: ToolRegistrar) -> Starlette:
    """Assemble the ASGI app for one MCP server."""
    server = MCPServer(component)
    register_tools(server)

    # DNS-rebinding protection is on by default and matches Host headers
    # exactly, answering 421 to anything unrecognised. The orchestrator dials
    # the compose service name and the healthcheck dials loopback, so both are
    # listed; see common.servers.allowed_hosts.
    security = TransportSecuritySettings(allowed_hosts=allowed_hosts(component))
    app = server.streamable_http_app(transport_security=security)

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse(health_payload(component))

    # Added to the app the SDK built rather than mounting that app inside our
    # own, which would leave its session manager's lifespan unstarted.
    app.router.add_route(HEALTH_PATH, healthz, methods=["GET"])

    return app


def run_server(component: str, register_tools: ToolRegistrar) -> None:
    """Serve one MCP server until the process is stopped."""
    uvicorn.run(
        build_app(component, register_tools),
        host=BIND_HOST,
        port=SERVER_PORT,
        log_level="info",
    )
