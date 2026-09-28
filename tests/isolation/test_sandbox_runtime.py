"""Phase 7.2's isolation tests: the sandbox boundary, checked at runtime.

tests/test_compose_isolation.py reads docker-compose.yml and checks that the
boundary is declared. This checks that it holds -- that the outbound call
actually fails, the write outside /scratch actually errors, and the runaway
tool is actually killed. A declaration and a behaviour are not the same claim,
and the one that matters when a researcher uploads an .rds file is the
behaviour.

Requires the compose stack. Marked `docker`, so the fast suite skips it; CI
runs it after `docker compose up --wait` with BIOGENT_REQUIRE_DOCKER_STACK set,
which turns a skip into a failure.
"""

import json
import re
import time

import pytest

from common.tooling import TOOL_TIMEOUT_SECONDS
from tests.isolation.conftest import (
    ALL_SERVICES,
    ORCHESTRATOR,
    SANDBOX_SERVICES,
    exec_in,
    running_services,
)

pytestmark = pytest.mark.docker

# An address outside the host, used by IP. A hostname would only prove that
# DNS is unavailable, and a sandbox with a route out but no resolver is still
# a sandbox with a route out.
EXTERNAL_IP = "1.1.1.1"
EXTERNAL_PORT = 443

# /proc/net/route lists the gateway per route in hex. A default route has
# destination 00000000 and a non-zero gateway; an on-link subnet route has a
# zero gateway, which is what an internal network gives a container.
ROUTE_COLUMNS = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)")

# Substrings that betray a credential in an environment. Matched case
# insensitively against variable names only.
CREDENTIAL_NAME_MARKERS = [
    "ANTHROPIC",
    "AWS",
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "_KEY",
    "DATABASE_URL",
]

# GPG_KEY is set by the official python image and holds the public fingerprint
# CPython releases are signed with. It matches "_KEY" and is not a credential;
# naming it here is cheaper than a pattern loose enough to miss a real one.
PUBLIC_VARIABLE_NAMES = {"GPG_KEY"}

SCRATCH_FILE = "/scratch/isolation-probe"
READ_ONLY_FILE = "/app/isolation-probe"


@pytest.mark.parametrize("service", SANDBOX_SERVICES)
def test_a_sandbox_cannot_reach_the_internet(service: str) -> None:
    """By IP, so a missing resolver cannot be mistaken for a missing route."""
    result = exec_in(
        service,
        "bash",
        "-c",
        f"exec 3<>/dev/tcp/{EXTERNAL_IP}/{EXTERNAL_PORT}",
        timeout=60,
    )

    assert result.returncode != 0, (
        f"{service} opened a connection to {EXTERNAL_IP}:{EXTERNAL_PORT}. "
        "An analysis sandbox must have no outbound route -- see DESIGN.md."
    )
    assert "unreachable" in result.output.lower(), (
        f"{service} failed to connect, but not because the network is "
        f"unreachable: {result.output.strip()}"
    )


@pytest.mark.parametrize("service", SANDBOX_SERVICES)
def test_a_sandbox_has_no_default_route(service: str) -> None:
    result = exec_in(service, "cat", "/proc/net/route", timeout=60)
    assert result.returncode == 0, result

    for line in result.stdout.splitlines()[1:]:
        match = ROUTE_COLUMNS.match(line)
        if not match:
            continue
        _, destination, gateway = match.groups()
        is_default_route = destination == "00000000" and gateway != "00000000"
        assert not is_default_route, (
            f"{service} has a default route via {gateway}. Its networks are "
            "supposed to be internal, which means no gateway at all."
        )


@pytest.mark.parametrize("service", SANDBOX_SERVICES)
def test_a_sandbox_cannot_reach_the_database(service: str) -> None:
    result = exec_in(service, "bash", "-c", "exec 3<>/dev/tcp/postgres/5432", timeout=60)

    assert result.returncode != 0, (
        f"{service} connected to postgres. Only the orchestrator shares a "
        "network with the database."
    )


@pytest.mark.parametrize("service", SANDBOX_SERVICES)
def test_a_sandbox_can_write_only_to_scratch(service: str) -> None:
    outside = exec_in(service, "sh", "-c", f"echo probe > {READ_ONLY_FILE}", timeout=60)
    assert outside.returncode != 0, (
        f"{service} wrote to {READ_ONLY_FILE}. Everything outside the scratch "
        "directory must be read-only."
    )
    assert "read-only" in outside.output.lower(), outside.output.strip()

    inside = exec_in(
        service,
        "sh",
        "-c",
        f"echo probe > {SCRATCH_FILE} && rm {SCRATCH_FILE}",
        timeout=60,
    )
    assert inside.returncode == 0, (
        f"{service} cannot write to its scratch directory, so tools have "
        f"nowhere to put intermediates: {inside.output.strip()}"
    )


@pytest.mark.parametrize("service", SANDBOX_SERVICES)
def test_a_sandbox_environment_holds_no_credentials(service: str) -> None:
    result = exec_in(service, "env", timeout=60)
    assert result.returncode == 0, result

    for line in result.stdout.splitlines():
        name = line.split("=", 1)[0].upper()
        if name in PUBLIC_VARIABLE_NAMES:
            continue
        for marker in CREDENTIAL_NAME_MARKERS:
            assert marker not in name, (
                f"{service} has {name} in its environment. A sandbox holds no "
                "credentials: the researcher's key stays in the orchestrator, "
                "and nothing here may carry a database URL or a cloud key."
            )


def test_the_graph_reaches_every_server() -> None:
    """Phase 7.2's checkpoint: the graph completes tool calls to all servers."""
    result = exec_in(ORCHESTRATOR, "python", "-m", "orchestrator.graph")
    assert result.returncode == 0, result

    reported = json.loads(result.stdout)
    assert set(reported) == set(SANDBOX_SERVICES), reported

    for service, runtime in reported.items():
        assert runtime["component"] == service, runtime
        assert runtime["packages"], f"{service} reported no package versions"

    languages = {runtime["language"] for runtime in reported.values()}
    assert languages == {"python", "r"}, (
        f"expected both runtimes to answer, got {languages}"
    )


def test_a_runaway_tool_is_killed_at_the_timeout() -> None:
    """The fourth isolation property, through the real MCP call path."""
    # A script rather than a one-liner: the try/except does not survive
    # semicolon joining, and the elapsed time is measured inside the
    # orchestrator so it excludes docker exec startup.
    script = (
        "import asyncio, json, time\n"
        "from common.tooling import TOOL_TIMEOUT_SECONDS\n"
        "from orchestrator.mcp_client import call_tool, ToolCallFailed\n"
        "async def main():\n"
        "    started = time.monotonic()\n"
        "    try:\n"
        "        await call_tool('python-analysis', 'diagnostics_busy_wait',\n"
        "                        {'seconds': TOOL_TIMEOUT_SECONDS * 3})\n"
        "        outcome = 'completed'\n"
        "    except ToolCallFailed as error:\n"
        "        outcome = 'failed'\n"
        "        print(json.dumps({'outcome': outcome,\n"
        "                          'elapsed': time.monotonic() - started,\n"
        "                          'message': str(error)}))\n"
        "        return\n"
        "    print(json.dumps({'outcome': outcome,\n"
        "                      'elapsed': time.monotonic() - started}))\n"
        "asyncio.run(main())\n"
    )

    started = time.monotonic()
    result = exec_in(ORCHESTRATOR, "python", "-c", script)
    assert result.returncode == 0, result

    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["outcome"] == "failed", (
        "a tool asked to run for three times the limit returned successfully, "
        "so nothing enforced the limit."
    )
    assert "exceeded" in report["message"], (
        f"the call failed, but not visibly as a timeout: {report['message']}"
    )

    elapsed = time.monotonic() - started
    assert elapsed < TOOL_TIMEOUT_SECONDS * 2, (
        f"the call took {elapsed:.0f}s against a {TOOL_TIMEOUT_SECONDS:g}s "
        "limit, so it was not killed at the deadline."
    )


def test_no_tool_process_is_left_running() -> None:
    """A timeout that abandons work instead of killing it is not a timeout.

    Runs after the timeout test. Reads /proc directly because the slim image
    has no ps, and looks for spawn_main rather than the tool's own name: a
    spawned child's command line is multiprocessing's bootstrap, so searching
    for "busy_wait" would find nothing even when a process had survived.
    """
    list_command_lines = (
        'for process in /proc/[0-9]*; do '
        'tr "\\0" " " < "$process/cmdline" 2>/dev/null; echo; done'
    )
    result = exec_in("python-analysis", "sh", "-c", list_command_lines, timeout=60)
    assert result.returncode == 0, result

    # The resource tracker is a long-lived helper the spawn context starts
    # once; it is not tool work. A running spawn_main is.
    leftovers = [line for line in result.stdout.splitlines() if "spawn_main" in line]
    assert not leftovers, (
        f"a tool child survived its timeout: {leftovers}. The sandbox is "
        "still burning CPU on work nobody is waiting for."
    )


def test_every_service_is_still_running() -> None:
    """Runs last: a tool call must not be able to take a server down.

    The R server enforces its timeout with setTimeLimit, which applies to the
    current top-level computation. Set and not cleared, that computation is
    the server's own event loop, and the server exits some seconds after the
    tool returns -- long after the call that caused it looked successful. This
    assertion, at the end of a suite that takes longer than the limit, is what
    catches that class of bug.
    """
    services = running_services()
    stopped = [name for name in ALL_SERVICES if name not in services]

    assert not stopped, (
        f"{stopped} stopped while the isolation tests ran. Something in a "
        "tool call took a container down."
    )
