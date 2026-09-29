# runtime.py
# Builds the runtime version report every server exposes as its first tool.
#
# This is not a placeholder tool that gets deleted later. DESIGN.md requires
# every analysis tool to log the package versions it ran under, and a report
# whose numbers cannot be traced to a specific stack is not reproducible. This
# is the piece that answers "which stack" -- it just happens to also be the
# simplest possible thing to call while the rest is being built.

from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError, version

# Recorded when a package the caller asked about is not installed. An absent
# package is a real answer about the environment, not an error.
NOT_INSTALLED = "not installed"


def runtime_report(component: str, packages: tuple[str, ...]) -> dict[str, object]:
    """Describe the interpreter and packages this server is running under."""
    return {
        "component": component,
        "language": "python",
        "language_version": platform.python_version(),
        "implementation": sys.implementation.name,
        "packages": {name: _version_of(name) for name in packages},
    }


def _version_of(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return NOT_INSTALLED
