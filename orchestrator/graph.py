# graph.py
# The minimal LangGraph graph: one node per analysis server, each calling that
# server's runtime_versions tool and recording the answer.
#
# It computes nothing and calls no model. What it proves is the wiring -- that
# the orchestrator can reach every sandbox over MCP and get a real tool result
# back -- which is Phase 7.2's checkpoint. The discovery funnel described in
# DESIGN.md replaces this graph; the client path underneath it stays.

from __future__ import annotations

import asyncio
import json
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from common.servers import ANALYSIS_SERVERS
from orchestrator.mcp_client import call_tool

# The tool every server exposes. Named once so a rename cannot half-land.
RUNTIME_TOOL = "runtime_versions"


def _merge(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    """Reducer for concurrent node writes into one dict."""
    return {**left, **right}


class ProbeState(TypedDict):
    # The nodes run in parallel, so the state needs a reducer: without one,
    # LangGraph rejects two nodes writing the same key in one superstep.
    runtimes: Annotated[dict[str, object], _merge]


def _probe_node(server: str):
    """Build the node that probes one server."""

    async def probe(_: ProbeState) -> ProbeState:
        return {"runtimes": {server: await call_tool(server, RUNTIME_TOOL)}}

    probe.__name__ = f"probe_{server.replace('-', '_')}"
    return probe


def build_graph():
    """A fan-out over the analysis servers, joined at the end."""
    builder = StateGraph(ProbeState)

    for server in ANALYSIS_SERVERS:
        node = _probe_node(server)
        builder.add_node(node.__name__, node)
        builder.add_edge(START, node.__name__)
        builder.add_edge(node.__name__, END)

    return builder.compile()


async def probe_all() -> dict[str, object]:
    """Run the graph and return what each server reported."""
    result = await build_graph().ainvoke({"runtimes": {}})
    return result["runtimes"]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(probe_all()), indent=2))
