# main.py
# Entry point for the Python analysis sandbox. Serves the health endpoint until
# Phase 7.2 puts an MCP server on this port; the scanpy-side analysis tools
# follow in 7.4.
#
# Nothing in this container may hold a credential or reach the network: see
# DESIGN.md, "sandbox isolation requirements".

from common.health import serve

COMPONENT = "python-analysis"

if __name__ == "__main__":
    serve(COMPONENT)
