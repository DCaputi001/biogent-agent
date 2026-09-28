"""Shared plumbing for the runtime isolation tests.

These run against the live compose stack, so they need `docker compose up -d
--wait` first. Everything here is about talking to that stack; the assertions
are in test_sandbox_runtime.py.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Set in CI. Without it these tests skip when the stack is down, which is the
# right behaviour on a laptop; with it they fail instead, because a security
# test that skips in CI reports green while checking nothing.
REQUIRE_STACK_ENV = "BIOGENT_REQUIRE_DOCKER_STACK"

SANDBOX_SERVICES = ["python-analysis", "r-analysis", "data-access"]
ORCHESTRATOR = "orchestrator"
ALL_SERVICES = [ORCHESTRATOR, "postgres", *SANDBOX_SERVICES]

COMMAND_TIMEOUT_SECONDS = 180


class CommandResult:
    """The outcome of one command run inside a container."""

    def __init__(self, completed: subprocess.CompletedProcess[str]) -> None:
        self.returncode = completed.returncode
        self.stdout = completed.stdout or ""
        self.stderr = completed.stderr or ""

    @property
    def output(self) -> str:
        return f"{self.stdout}\n{self.stderr}"

    def __repr__(self) -> str:
        return f"CommandResult(returncode={self.returncode}, output={self.output!r})"


def compose(*arguments: str, timeout: int = COMMAND_TIMEOUT_SECONDS) -> CommandResult:
    """Run a docker compose command against this repo's stack."""
    return CommandResult(
        subprocess.run(
            ["docker", "compose", *arguments],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    )


def exec_in(service: str, *command: str, timeout: int = COMMAND_TIMEOUT_SECONDS) -> CommandResult:
    """Run a command inside a running service container.

    -T because there is no TTY in CI, and the tests read stdout.
    """
    return compose("exec", "-T", service, *command, timeout=timeout)


def running_services() -> set[str]:
    result = compose("ps", "--format", "json", timeout=60)
    if result.returncode != 0:
        return set()

    # `compose ps --format json` emits one JSON object per line.
    services = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("State") == "running":
            services.add(entry.get("Service"))
    return services


@pytest.fixture(scope="session", autouse=True)
def stack() -> set[str]:
    """Require the compose stack, or skip -- unless CI says it must be there."""
    services = running_services()
    missing = [name for name in ALL_SERVICES if name not in services]

    if missing:
        message = (
            f"the compose stack is not running (missing: {', '.join(missing)}). "
            "Start it with `docker compose up -d --wait`."
        )
        if os.environ.get(REQUIRE_STACK_ENV):
            pytest.fail(message)
        pytest.skip(message)

    return services
