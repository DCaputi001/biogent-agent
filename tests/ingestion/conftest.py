"""Plumbing for the ingestion tests: calling MCP tools through the stack.

Reuses the compose helpers from tests/isolation/conftest.py rather than
growing a second copy of them. The one thing added here is calling a tool:
the orchestrator is the only container that can reach the servers, so a tool
call from the host is a python -c inside the orchestrator.
"""

import json
import textwrap

import pytest

from tests.fixtures import spec
from tests.isolation.conftest import ORCHESTRATOR, exec_in

# Raised inside the orchestrator and reported back as a structured failure,
# so a test can tell "the tool said no" from "the call never happened".
_CALL_SCRIPT = textwrap.dedent(
    """
    import asyncio, json, sys
    from orchestrator.mcp_client import call_tool, ToolCallFailed

    server, tool, arguments = json.loads(sys.argv[1])

    async def main():
        try:
            result = await call_tool(server, tool, arguments)
        except ToolCallFailed as error:
            print(json.dumps({"ok": False, "error": str(error)}))
            return
        print(json.dumps({"ok": True, "result": result}))

    asyncio.run(main())
    """
)


class ToolRefused(AssertionError):
    """The server returned an error result for the call."""


def call_tool(server: str, tool: str, **arguments: object) -> object:
    """Call an MCP tool from inside the orchestrator and return its result."""
    outcome = _call(server, tool, arguments)
    if not outcome["ok"]:
        raise ToolRefused(outcome["error"])
    return outcome["result"]


def call_tool_expecting_failure(server: str, tool: str, **arguments: object) -> str:
    """Call a tool that should be refused, and return the error message."""
    outcome = _call(server, tool, arguments)
    assert not outcome["ok"], (
        f"{server}.{tool} succeeded with {arguments}, and should not have: "
        f"{outcome.get('result')!r}"
    )
    return outcome["error"]


def _call(server: str, tool: str, arguments: dict[str, object]) -> dict:
    payload = json.dumps([server, tool, arguments])
    result = exec_in(ORCHESTRATOR, "python", "-c", _CALL_SCRIPT, payload)
    assert result.returncode == 0, result

    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="session", autouse=True)
def fixtures_present() -> None:
    """Fail loudly when the fixtures were never generated.

    Without this the ingestion tests fail one by one with "no dataset", which
    reads like a bug in the resolver rather than a missing setup step.
    """
    from tests.isolation.conftest import REPO_ROOT

    expected = [
        (spec.H5AD_DATASET_ID, spec.H5AD_FILENAME),
        (spec.RDS_DATASET_ID, spec.RDS_FILENAME),
        (spec.MALFORMED_DATASET_ID, spec.MALFORMED_FILENAME),
    ]
    missing = [
        f"{dataset_id}/{filename}"
        for dataset_id, filename in expected
        if not (REPO_ROOT / "data" / "uploads" / dataset_id / filename).is_file()
    ]

    if missing:
        pytest.fail(
            f"test fixtures are missing: {missing}. "
            "Generate them with `sh scripts/generate-fixtures.sh`."
        )
