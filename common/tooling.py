# tooling.py
# Wall-clock enforcement for analysis tools. Exposes run_with_timeout(), which
# every tool body in every Python MCP server goes through, and the exception
# types a caller can distinguish.
#
# A tool that never returns is not a hypothetical here: analysis on a real
# dataset can diverge, and the sandbox it runs in has a CPU limit but no time
# limit. Without this, a runaway tool holds a container at its CPU ceiling for
# as long as the stack is up.

from __future__ import annotations

import multiprocessing
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

# The default ceiling for a single tool call. Analysis tools that legitimately
# run longer get an explicit, larger value at their call site rather than a
# raised default -- the point of a default is that exceeding it is unusual.
TOOL_TIMEOUT_SECONDS = 30.0

# How long to wait for a killed child to be reaped before giving up on it.
_REAP_TIMEOUT_SECONDS = 5.0


class ToolTimeout(RuntimeError):
    """A tool exceeded its wall-clock limit and its process was killed."""


class ToolExecutionError(RuntimeError):
    """A tool raised. The original type name is preserved in the message."""


def run_with_timeout(
    func: Callable[..., Any],
    *args: Any,
    seconds: float = TOOL_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> Any:
    """Run func in a child process, killing it if it outlives the deadline.

    A child process rather than a thread or a signal alarm, because neither of
    those can interrupt the case this exists for: a tight loop inside a C
    extension never yields to the interpreter, so it never sees an exception
    set on its thread and never runs a signal handler. A process can always be
    killed by the OS.
    """
    # spawn, not fork: a forked child inherits the server's event loop, open
    # sockets and any partially-held locks, and an analysis tool that touches
    # them corrupts the parent. The cost is a fresh interpreter per call, which
    # is noise next to the runtime of real analysis.
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)

    process = context.Process(
        target=_run_and_report,
        args=(sender, func, args, kwargs),
        daemon=True,
    )
    process.start()
    sender.close()

    try:
        process.join(seconds)
        if process.is_alive():
            process.kill()
            process.join(_REAP_TIMEOUT_SECONDS)
            raise ToolTimeout(
                f"{_describe(func)} exceeded its {seconds:g}s limit and was killed."
            )
        return _unwrap(receiver, process, func)
    finally:
        receiver.close()
        # A killed child is already gone; close() releases the handles either
        # way, so a caller cannot leak one process per timed-out call.
        process.close()


def _run_and_report(
    sender: Connection,
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    """Child-process entry point: run the call, report one outcome, exit."""
    try:
        sender.send(("ok", func(*args, **kwargs)))
    except BaseException as error:  # noqa: BLE001 - reported, not swallowed
        # The exception instance may not be picklable, and a pickling failure
        # here would look identical to a crash. Send the description instead.
        sender.send(("error", f"{type(error).__name__}: {error}"))
    finally:
        sender.close()


def _unwrap(receiver: Connection, process: Any, func: Callable[..., Any]) -> Any:
    """Turn the child's one message, or its silence, into a result."""
    if not receiver.poll():
        raise ToolExecutionError(
            f"{_describe(func)} exited with code {process.exitcode} "
            "without returning a result."
        )

    outcome, payload = receiver.recv()
    if outcome == "error":
        raise ToolExecutionError(f"{_describe(func)} failed: {payload}")
    return payload


def _describe(func: Callable[..., Any]) -> str:
    return getattr(func, "__qualname__", repr(func))
