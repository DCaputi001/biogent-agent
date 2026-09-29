# diagnostics.py
# Deliberately misbehaving work, used to prove that the sandbox's protections
# actually fire. Nothing here analyses anything.
#
# It lives in common/ rather than inside a server's entry module because
# run_with_timeout runs its target in a spawned child, which re-imports the
# function by module path; a stable importable module makes that work however
# the server was launched.

from __future__ import annotations

import time


def busy_wait(seconds: float) -> str:
    """Occupy the CPU for a while without sleeping.

    A sleep would be killed by any timeout mechanism, including ones that
    cannot interrupt real work. Spinning is the case that matters: it is what
    a diverging analysis looks like, and it is why the timeout kills a process
    instead of raising in a thread.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        pass
    return f"spun for {seconds:g}s"
