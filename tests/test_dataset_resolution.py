"""Dataset IDs resolve to one place, and nothing else resolves at all.

DESIGN.md: "the agent never constructs a file path." The agent asks for a
dataset by opaque ID, and common/datasets.py is the only thing that turns an
ID into a location. That makes this module the boundary an injected
instruction would have to get through -- the contents of an uploaded file are
read by a model in this system, and "open ../../other-researcher/data.rds" is
the request it must be impossible to express.

These tests are the traversal cases. The runtime half, that the same rejection
happens inside the sandboxes, is in tests/ingestion/.
"""

import re
from pathlib import Path

import pytest

from common.datasets import (
    DATASET_ID_PATTERN,
    FILENAME_PATTERN,
    InvalidDatasetId,
    InvalidFilename,
    upload_root,
    validate_dataset_id,
    validate_filename,
    workspace_root,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

VALID_ID = "00000000-0000-4000-8000-000000000001"

# Every one of these is a way of naming a file somewhere else.
TRAVERSAL_IDS = [
    "..",
    "../..",
    "../other-researcher",
    "/etc",
    "/data/uploads/../../etc",
    "C:\\Windows",
    "..\\..\\windows",
    "0000000/../../etc",
    "0000%2e%2e",
    "00000000\n/etc",
    "00000000-0000-4000-8000-000000000001/../../etc",
]

MALFORMED_IDS = [
    "",
    "short",
    "UPPERCASE-0000-4000-8000-000000000001",
    "not hex at all!",
    "0" * 65,
    ".hidden-0000-4000-8000-000000000001",
]

TRAVERSAL_FILENAMES = [
    "../fixture.rds",
    "../../etc/passwd",
    "/etc/passwd",
    "sub/dir/fixture.rds",
    "..\\fixture.rds",
    ".ssh",
    "",
]


@pytest.mark.parametrize("dataset_id", TRAVERSAL_IDS + MALFORMED_IDS)
def test_a_dataset_id_that_is_not_an_id_is_rejected(dataset_id: str) -> None:
    with pytest.raises(InvalidDatasetId):
        validate_dataset_id(dataset_id)


@pytest.mark.parametrize("filename", TRAVERSAL_FILENAMES)
def test_a_filename_that_is_not_a_filename_is_rejected(filename: str) -> None:
    with pytest.raises(InvalidFilename):
        validate_filename(filename)


def test_a_valid_id_is_accepted() -> None:
    """Guards against a pattern so strict it rejects everything."""
    assert validate_dataset_id(VALID_ID) == VALID_ID
    assert validate_filename("fixture.h5ad") == "fixture.h5ad"


def test_a_dataset_id_is_not_a_type_confusion() -> None:
    """A non-string ID must not reach the filesystem layer."""
    for value in (None, 42, ["a"], {"id": VALID_ID}):
        with pytest.raises(InvalidDatasetId):
            validate_dataset_id(value)  # type: ignore[arg-type]


def test_roots_stay_inside_their_volumes() -> None:
    assert str(upload_root(VALID_ID)).replace("\\", "/").endswith(
        f"data/uploads/{VALID_ID}"
    )
    assert str(workspace_root(VALID_ID)).replace("\\", "/").endswith(
        f"data/workspace/{VALID_ID}"
    )


def test_the_r_resolver_uses_the_same_patterns() -> None:
    """servers/r-analysis/datasets.R duplicates these patterns by necessity.

    The two sandboxes must resolve one ID to one file, or a cross-check
    between the Python and R views of a dataset compares different data. The
    duplication is unavoidable across runtimes; the drift is not.
    """
    r_source = (REPO_ROOT / "servers" / "r-analysis" / "datasets.R").read_text()

    for name, pattern in (
        ("DATASET_ID_PATTERN", DATASET_ID_PATTERN.pattern),
        ("FILENAME_PATTERN", FILENAME_PATTERN.pattern),
    ):
        match = re.search(rf'^{name} <- "(.+)"$', r_source, re.MULTILINE)
        assert match, f"{name} is not defined in datasets.R"
        assert match.group(1) == pattern, (
            f"{name} differs between common/datasets.py and datasets.R:\n"
            f"  python: {pattern}\n  r:      {match.group(1)}"
        )
