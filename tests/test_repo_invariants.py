"""Structural checks on the repo itself.

Two of Phase 7.1's checkpoints are properties of the repository rather than of
any code in it -- "the repo has no secrets configured" and "no deploy job" --
and a property nobody checks is a property that quietly stops holding. These
tests are how those stay true while the repo grows.

The other invariant here is that every path is relative to the repo root.
Everything in this repo is eventually moved into services/bio-agent/ in the
main BioGent repo, and an absolute path or a parent-directory reference is
what would turn that move from a rename into a debugging session.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# The layout the import depends on: these map one-to-one onto
# services/bio-agent/* in the main repo.
EXPECTED_DIRECTORIES = [
    "orchestrator",
    "servers/python-analysis",
    "servers/r-analysis",
    "servers/data-access",
    "evals",
]

# Words that should never appear in this repo's CI. Deploying from here is not
# "not implemented yet" -- it is the security boundary. This repo loads
# uploaded .rds files, and R deserialization is a known RCE path
# (CVE-2024-27322); credentials that can reach production must not be one
# compromised workflow away from that code.
FORBIDDEN_CI_PATTERNS = [
    r"aws-actions/",
    r"AWS_ACCESS_KEY_ID",
    r"AWS_SECRET_ACCESS_KEY",
    r"role-to-assume",
    # Word-bounded: an unanchored "ecr" matches inside "secret", which would
    # fail this test on the very comment explaining that there are no secrets.
    r"\becr\b",
    r"\becs\b",
    r"\bterraform\b",
]

# gitleaks is the one legitimate reason a secret-ish word appears in CI: the
# job that scans for committed credentials. Its own lines are exempt.
SECRET_SCAN_ALLOWLIST = re.compile(r"gitleaks|GITHUB_TOKEN", re.IGNORECASE)


def _workflow_files() -> list[Path]:
    return sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("relative_path", EXPECTED_DIRECTORIES)
def test_expected_directory_exists(relative_path: str) -> None:
    assert (REPO_ROOT / relative_path).is_dir(), (
        f"{relative_path}/ is missing. The import into services/bio-agent/ "
        "assumes this layout."
    )


@pytest.mark.parametrize("relative_path", EXPECTED_DIRECTORIES)
def test_expected_directory_survives_a_clone(relative_path: str) -> None:
    """Git does not track empty directories, so each needs a placeholder.

    Without one, the directory exists here and is simply absent after a clone
    onto the laptop -- the failure mode CONTRIBUTING.md in the main repo
    already documents.
    """
    directory = REPO_ROOT / relative_path
    tracked_content = [p for p in directory.rglob("*") if p.is_file()]
    assert tracked_content, (
        f"{relative_path}/ is empty and has no .gitkeep, so it will not "
        "survive a fresh clone."
    )


def test_ci_workflows_exist() -> None:
    assert _workflow_files(), "No CI workflow found under .github/workflows/."


@pytest.mark.parametrize("pattern", FORBIDDEN_CI_PATTERNS)
def test_ci_has_no_path_to_production(pattern: str) -> None:
    """No deploy job, no cloud credentials, no infrastructure. On purpose."""
    compiled = re.compile(pattern, re.IGNORECASE)

    for workflow in _workflow_files():
        for line_number, line in enumerate(workflow.read_text().splitlines(), 1):
            # Comments are exempt: a comment cannot deploy anything, and the
            # comment explaining why there is no deploy job necessarily names
            # the things that are absent.
            if line.lstrip().startswith("#") or SECRET_SCAN_ALLOWLIST.search(line):
                continue
            assert not compiled.search(line), (
                f"{workflow.name}:{line_number} matches {pattern!r}. This repo "
                "deliberately has no deploy path -- see AGENTS.md. Deployment "
                "belongs to the main BioGent repo, after the import."
            )


def test_ci_workflows_parse() -> None:
    for workflow in _workflow_files():
        parsed = yaml.safe_load(workflow.read_text())
        assert parsed.get("jobs"), f"{workflow.name} defines no jobs."


def test_compose_paths_are_relative_to_the_repo_root() -> None:
    """The whole tree moves to services/bio-agent/ at import.

    An absolute path, or one reaching above the repo root with '..', works
    here and breaks silently there.
    """
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())

    for name, service in (compose.get("services") or {}).items():
        for volume in service.get("volumes") or []:
            host_path = volume.split(":")[0] if isinstance(volume, str) else ""
            assert not host_path.startswith(("/", "~")), (
                f"service {name!r} mounts an absolute host path: {volume}"
            )
            assert ".." not in host_path, (
                f"service {name!r} mounts a path outside the repo: {volume}"
            )

        build = service.get("build")
        context = build.get("context") if isinstance(build, dict) else build
        if context:
            assert not str(context).startswith(("/", "~")) and ".." not in str(context), (
                f"service {name!r} builds from outside the repo: {context}"
            )


def test_the_plan_file_is_ignored() -> None:
    """BIOGENT_PLAN.md must never be committable from any clone."""
    ignore_rules = (REPO_ROOT / ".gitignore").read_text().splitlines()
    assert "BIOGENT_PLAN.md" in [line.strip() for line in ignore_rules], (
        "BIOGENT_PLAN.md is not listed in .gitignore by exact name."
    )
