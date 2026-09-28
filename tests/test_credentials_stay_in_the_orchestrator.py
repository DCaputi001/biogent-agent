"""The researcher's API key must never reach a sandbox.

INTEGRATION_CONTRACT.md section 2: the key arrives per request, is used by the
orchestrator, and is never persisted -- and, stricter than the RAG service
needs to be, never passed to an MCP server, because those containers open
untrusted files and a credential in one is a credential that can be
exfiltrated by whatever was just opened.

The runtime check that a sandbox container's environment holds no secrets
lives in tests/isolation/. This is the static half: no code that ships inside
a sandbox image may so much as mention a credential, and the transport between
the orchestrator and the servers must have nowhere to put one.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Everything copied into a sandbox image: the servers' own code, plus the
# shared modules every image carries.
SANDBOX_SOURCE_DIRECTORIES = ["servers", "common"]

# Names that only appear in code that handles a credential. Matched case
# insensitively, so a lowercase variable is caught too.
CREDENTIAL_PATTERNS = [
    r"ANTHROPIC_API_KEY",
    r"X-Anthropic-Api-Key",
    r"api_key",
    r"AWS_SECRET_ACCESS_KEY",
    r"DATABASE_URL",
    r"Authorization",
]

# Source that ends up in an image, by extension, plus the Dockerfiles that
# build it. Listing what counts rather than what does not keeps compiled
# artefacts and editor droppings out of the scan.
SOURCE_SUFFIXES = {".py", ".R", ".r", ".sh"}
SOURCE_FILENAMES = {"Dockerfile"}


def _sandbox_sources() -> list[Path]:
    files: list[Path] = []
    for directory in SANDBOX_SOURCE_DIRECTORIES:
        for path in sorted((REPO_ROOT / directory).rglob("*")):
            if not path.is_file():
                continue
            if path.suffix in SOURCE_SUFFIXES or path.name in SOURCE_FILENAMES:
                files.append(path)
    return files


def test_there_are_sandbox_sources_to_check() -> None:
    """Guards against the scan below passing because it found nothing."""
    assert _sandbox_sources()


@pytest.mark.parametrize("pattern", CREDENTIAL_PATTERNS)
def test_no_sandbox_source_mentions_a_credential(pattern: str) -> None:
    compiled = re.compile(pattern, re.IGNORECASE)

    for source in _sandbox_sources():
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), 1
        ):
            # A comment explaining why there is no credential here necessarily
            # names one. Code may not.
            if line.lstrip().startswith("#"):
                continue
            relative = source.relative_to(REPO_ROOT).as_posix()
            assert not compiled.search(line), (
                f"{relative}:{line_number} mentions {pattern!r}. Code that "
                "ships inside a sandbox must not handle credentials -- the "
                "researcher's key stays in the orchestrator."
            )


def test_the_client_cannot_be_given_a_credential() -> None:
    """call_tool takes a server, a tool and arguments. Nothing else."""
    import inspect

    from orchestrator.mcp_client import call_tool

    parameters = set(inspect.signature(call_tool).parameters)
    assert parameters == {"server", "tool", "arguments", "timeout"}, (
        "orchestrator.mcp_client.call_tool grew a parameter. If it is a way "
        "to pass a header or a token to a sandbox, it must not exist."
    )
