# main.py
# The Python analysis sandbox, as an MCP server. Holds the scanpy-side tools
# from 7.4 on; for now it holds the runtime report and one diagnostic.
#
# Nothing in this container may hold a credential or reach the network: see
# DESIGN.md, "sandbox isolation requirements". Every tool body runs through
# run_with_timeout, so no tool can occupy the sandbox indefinitely.

from mcp.server import MCPServer

from common.diagnostics import busy_wait
from common.mcp_app import run_server, run_tool
from common.runtime import runtime_report
from common.servers import PYTHON_ANALYSIS
from common.tooling import TOOL_TIMEOUT_SECONDS

# Packages whose versions belong in a methods section. The scientific stack
# joins this list as the analysis tools land.
REPORTED_PACKAGES = ("mcp", "uvicorn")

# Ceiling on what the diagnostic will accept, so a typo cannot ask for a spin
# measured in hours. Comfortably past the timeout it exists to trigger.
MAX_DIAGNOSTIC_SECONDS = TOOL_TIMEOUT_SECONDS * 10


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def runtime_versions() -> dict[str, object]:
        """Report the Python version and analysis package versions in use."""
        return run_tool(runtime_report, PYTHON_ANALYSIS, REPORTED_PACKAGES)

    @server.tool()
    def diagnostics_busy_wait(seconds: float) -> str:
        """Occupy the CPU for `seconds`. Diagnostic only; computes nothing.

        This exists so the wall-clock timeout can be tested through the real
        MCP call path rather than only in a unit test of the harness. Asking
        for longer than the timeout is the intended use, and it will fail.
        """
        capped = min(float(seconds), MAX_DIAGNOSTIC_SECONDS)
        return run_tool(busy_wait, capped)


if __name__ == "__main__":
    run_server(PYTHON_ANALYSIS, register_tools)
