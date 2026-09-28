# main.py
# The data access server, as an MCP server. From 7.3 this is the only component
# that turns an opaque dataset ID into a storage location -- the agent never
# constructs a path itself. For now it reports its runtime only.

from mcp.server import MCPServer

from common.mcp_app import run_server, run_tool
from common.runtime import runtime_report
from common.servers import DATA_ACCESS

REPORTED_PACKAGES = ("mcp", "uvicorn")


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def runtime_versions() -> dict[str, object]:
        """Report the Python version and package versions in use."""
        return run_tool(runtime_report, DATA_ACCESS, REPORTED_PACKAGES)


if __name__ == "__main__":
    run_server(DATA_ACCESS, register_tools)
