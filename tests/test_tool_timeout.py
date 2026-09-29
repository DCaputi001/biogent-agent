"""The wall-clock limit every analysis tool runs under.

DESIGN.md gives each sandbox a CPU and memory limit and a timeout. The first
two are container settings; the timeout is code, in common/tooling.py, and it
is the one that has to actually kill something. These tests are the fast half
of proving it -- the runtime half calls it through a real MCP server in
tests/isolation/.

The case that matters is a tool that does not cooperate. A thread cannot be
interrupted and a signal handler does not run inside a tight loop, so the
harness runs tool bodies in a child process it can kill outright; the busy-wait
test below is what distinguishes that from a mechanism that only works on
well-behaved code.
"""

import time

import pytest

from common.diagnostics import busy_wait
from common.tooling import (
    TOOL_TIMEOUT_SECONDS,
    ToolExecutionError,
    ToolTimeout,
    run_with_timeout,
)

# Short enough to keep the suite fast, long enough to survive the cost of
# starting a spawned interpreter on a loaded CI runner.
TEST_TIMEOUT_SECONDS = 2.0

# How far past the limit a kill may land before the mechanism is not really a
# limit. Generous: this asserts "it was killed", not scheduler precision.
KILL_SLACK_SECONDS = 15.0


def _return_value(value: int) -> int:
    return value


def _raise_value_error() -> None:
    raise ValueError("the tool decided this input was wrong")


def _exit_without_returning() -> None:
    raise SystemExit(3)


def test_a_normal_result_passes_through() -> None:
    assert run_with_timeout(_return_value, 42, seconds=TEST_TIMEOUT_SECONDS) == 42


def test_a_runaway_tool_is_killed_at_the_deadline() -> None:
    started = time.monotonic()

    with pytest.raises(ToolTimeout):
        run_with_timeout(
            busy_wait,
            TEST_TIMEOUT_SECONDS * 20,
            seconds=TEST_TIMEOUT_SECONDS,
        )

    elapsed = time.monotonic() - started
    assert elapsed < TEST_TIMEOUT_SECONDS + KILL_SLACK_SECONDS, (
        f"the call took {elapsed:.1f}s, so the deadline did not end it."
    )


def test_a_failing_tool_reports_its_failure() -> None:
    """A tool that raises must not look like a tool that returned nothing."""
    with pytest.raises(ToolExecutionError) as failure:
        run_with_timeout(_raise_value_error, seconds=TEST_TIMEOUT_SECONDS)

    assert "ValueError" in str(failure.value)
    assert "the tool decided this input was wrong" in str(failure.value)


def test_a_tool_that_dies_without_answering_is_an_error() -> None:
    """A crashed child must raise rather than return None as if it worked."""
    with pytest.raises(ToolExecutionError):
        run_with_timeout(_exit_without_returning, seconds=TEST_TIMEOUT_SECONDS)


def test_the_default_limit_is_finite() -> None:
    """A default of None or zero would disable the protection silently."""
    assert 0 < TOOL_TIMEOUT_SECONDS < 60 * 60
