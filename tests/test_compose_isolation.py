"""Static checks on the sandbox boundary declared in docker-compose.yml.

DESIGN.md gives the analysis sandboxes four properties: no network access, no
credentials, no database access, and a read-only filesystem apart from one
scratch directory. Three of those are compose settings, so they can be checked
by reading the file -- in milliseconds, on every PR, without a docker daemon.

This is the static half of that verification. The runtime half arrives in
Phase 7.2: an outbound call that actually fails, a write outside /scratch that
actually errors, and a runaway job that is actually killed at the timeout.
Neither half replaces the other. This one catches the edit that attaches a
sandbox to an egress network months from now, in review, rather than in a
trace nobody is reading.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# The containers that will hold untrusted data and researcher code paths. A
# new one is added here deliberately, which is the point: the checks below are
# opt-out only by editing this list, and that edit is visible in review.
SANDBOX_SERVICES = ["python-analysis", "r-analysis", "data-access"]

# The one component allowed to straddle the boundary: it holds the API key,
# reaches the model, and talks to the database.
ORCHESTRATOR_SERVICE = "orchestrator"

DATABASE_SERVICE = "postgres"

# Credential-bearing keys. A sandbox with any of these is a sandbox that can
# leak something to whatever it just opened.
CREDENTIAL_KEYS = ["environment", "env_file", "secrets"]

SCRATCH_PATH = "/scratch"

# The only mounts a sandbox may have, as "host:container" prefixes. A dataset
# has to reach the container somehow, and these two are how: uploads are what
# the researcher gave us, workspace is what we derive from it.
#
# This list replaced a blanket "a sandbox mounts no volumes" assertion when
# Phase 7.3 needed datasets to arrive. Weakening a test to make code pass is
# against the rules in AGENTS.md, so the replacement was flagged in review and
# is narrower in every other respect: the mounts are named, uploads must be
# read-only, and anything else still fails.
UPLOADS_MOUNT = "./data/uploads:/data/uploads"
WORKSPACE_MOUNT = "./data/workspace:/data/workspace"

ALLOWED_MOUNTS = {
    f"{UPLOADS_MOUNT}:ro",
    WORKSPACE_MOUNT,
}


def _compose() -> dict:
    return yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())


def _service(name: str) -> dict:
    services = _compose().get("services") or {}
    assert name in services, f"docker-compose.yml defines no {name!r} service."
    return services[name]


def _networks_of(service: dict) -> list[str]:
    """Compose accepts both a list and a mapping under `networks`."""
    networks = service.get("networks") or []
    return list(networks)


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_sandbox_is_on_internal_networks_only(service_name: str) -> None:
    """An internal network has no gateway, so there is no route off the host."""
    compose = _compose()
    declared_networks = compose.get("networks") or {}

    attached = _networks_of(compose["services"][service_name])
    assert attached, (
        f"{service_name} declares no networks, so compose puts it on the "
        "default bridge -- which has an outbound route."
    )

    for network_name in attached:
        definition = declared_networks.get(network_name) or {}
        assert definition.get("internal") is True, (
            f"{service_name} is attached to {network_name!r}, which is not "
            "marked internal. An analysis sandbox must have no outbound route "
            "at all -- see DESIGN.md."
        )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_sandbox_cannot_reach_the_database(service_name: str) -> None:
    database_networks = set(_networks_of(_service(DATABASE_SERVICE)))
    sandbox_networks = set(_networks_of(_service(service_name)))

    shared = database_networks & sandbox_networks
    assert not shared, (
        f"{service_name} shares {sorted(shared)} with {DATABASE_SERVICE}. "
        "Sandboxes get no database access; only the orchestrator does."
    )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_sandbox_publishes_no_host_port(service_name: str) -> None:
    """A published port is a hole straight through the internal network."""
    assert not _service(service_name).get("ports"), (
        f"{service_name} publishes a host port. Sandboxes are reachable from "
        "the orchestrator over the internal network and from nowhere else."
    )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
@pytest.mark.parametrize("key", CREDENTIAL_KEYS)
def test_sandbox_is_handed_no_credentials(service_name: str, key: str) -> None:
    assert key not in _service(service_name), (
        f"{service_name} defines {key!r}. Sandboxes hold no credentials: the "
        "researcher's API key never leaves the orchestrator, and nothing here "
        "may carry a database URL or a cloud key."
    )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_sandbox_filesystem_is_read_only_apart_from_scratch(service_name: str) -> None:
    service = _service(service_name)

    assert service.get("read_only") is True, (
        f"{service_name} does not set read_only. Everything outside the "
        "scratch directory must be unwritable."
    )

    tmpfs_mounts = service.get("tmpfs") or []
    assert SCRATCH_PATH in tmpfs_mounts, (
        f"{service_name} has no {SCRATCH_PATH} tmpfs. Tools need exactly one "
        "writable path, and a memory-backed one does not outlive the container "
        "holding a researcher's data."
    )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_a_sandbox_mounts_only_the_dataset_volumes(service_name: str) -> None:
    """Datasets arrive by bind mount; nothing else may."""
    for mount in _service(service_name).get("volumes") or []:
        assert mount in ALLOWED_MOUNTS, (
            f"{service_name} mounts {mount!r}. A sandbox may mount only "
            f"{sorted(ALLOWED_MOUNTS)} -- another writable path defeats "
            "read_only, and another host path is a way out of the repo."
        )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_a_sandbox_cannot_write_to_the_uploads_volume(service_name: str) -> None:
    """The original upload is evidence and must survive being analysed.

    The container most likely to corrupt a researcher's file is the one
    deserializing it, so no sandbox gets write access to the uploads.
    """
    mounts = _service(service_name).get("volumes") or []
    uploads = [mount for mount in mounts if mount.startswith(UPLOADS_MOUNT)]

    for mount in uploads:
        assert mount.endswith(":ro"), (
            f"{service_name} mounts the uploads volume as {mount!r}, which is "
            "writable. Uploads are read-only in every sandbox."
        )


def test_the_orchestrator_cannot_read_uploads() -> None:
    """The process holding the API key does not open researcher files.

    AGENTS.md's first rule: an uploaded .rds is untrusted code, and opening
    one anywhere that has credentials or a network route defeats the design.
    """
    mounts = _service(ORCHESTRATOR_SERVICE).get("volumes") or []
    assert not mounts, (
        f"the orchestrator mounts {mounts}. It holds the researcher's API key "
        "and has an egress route; it must not be able to read an upload."
    )


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_sandbox_has_resource_limits(service_name: str) -> None:
    """A runaway analysis must hit a ceiling rather than the host's."""
    service = _service(service_name)

    for limit in ("mem_limit", "cpus", "pids_limit"):
        assert service.get(limit), f"{service_name} sets no {limit}."


@pytest.mark.parametrize("service_name", SANDBOX_SERVICES)
def test_sandbox_drops_privileges(service_name: str) -> None:
    service = _service(service_name)

    assert service.get("cap_drop") == ["ALL"], (
        f"{service_name} does not drop all capabilities."
    )
    assert "no-new-privileges:true" in (service.get("security_opt") or []), (
        f"{service_name} allows privilege escalation via setuid binaries."
    )


def test_every_sandbox_network_member_is_a_known_sandbox() -> None:
    """Catches a new service quietly joining the sandbox network.

    Without this, adding a container to `sandbox` and forgetting to list it in
    SANDBOX_SERVICES would exempt it from every check above.
    """
    services = _compose().get("services") or {}

    members = {
        name
        for name, service in services.items()
        if "sandbox" in _networks_of(service)
    }
    expected = set(SANDBOX_SERVICES) | {ORCHESTRATOR_SERVICE}

    assert members == expected, (
        f"Services on the sandbox network are {sorted(members)}, expected "
        f"{sorted(expected)}. A new sandbox must be added to SANDBOX_SERVICES "
        "so the isolation checks apply to it."
    )
