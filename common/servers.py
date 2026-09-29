# servers.py
# The one registry of MCP server names and the URLs they are reachable at.
# Imported by the orchestrator to dial them and by the servers to declare which
# Host headers they accept, so the two cannot drift apart.
#
# These are plain URLs and nothing else. There is deliberately no field here
# for a header, a token or a key: the researcher's API key never leaves the
# orchestrator, and a registry that could carry one is a registry that
# eventually will.

from __future__ import annotations

# Every server listens on the same port; the compose service name is the host.
SERVER_PORT = 8000

# The Streamable HTTP endpoint the MCP SDK mounts by default.
MCP_PATH = "/mcp"

HEALTH_PATH = "/healthz"

ORCHESTRATOR = "orchestrator"
PYTHON_ANALYSIS = "python-analysis"
R_ANALYSIS = "r-analysis"
DATA_ACCESS = "data-access"

# The servers the orchestrator calls. The orchestrator itself is not in this
# list: it is the client.
ANALYSIS_SERVERS = (PYTHON_ANALYSIS, R_ANALYSIS, DATA_ACCESS)


def mcp_url(server: str) -> str:
    """The MCP endpoint for a server, addressed by its compose service name."""
    return f"http://{server}:{SERVER_PORT}{MCP_PATH}"


def allowed_hosts(server: str) -> list[str]:
    """Host header values a server accepts.

    The SDK enables DNS-rebinding protection by default and answers 421 to any
    Host it does not recognise. Inside compose the orchestrator dials the
    service name, and the container's own healthcheck dials loopback, so both
    have to be listed -- each with and without a port, because the check is an
    exact string match.
    """
    names = [server, "localhost", "127.0.0.1"]
    return [pattern for name in names for pattern in (name, f"{name}:*")]
