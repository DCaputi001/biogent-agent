# datasets.py
# Turns an opaque dataset ID into a location on disk, and refuses anything
# that is not one. Shared by the data-access server and the analysis
# sandboxes, so that every container derives the same path from the same ID.
#
# This is how DESIGN.md's "the agent never constructs a file path" survives
# being spread across three containers. A tool takes a dataset ID and a file
# name; it never takes a path, and it never returns one. Prompt injection from
# the contents of an uploaded file is a live concern in this system, and the
# defence is that there is no path-shaped input to inject into.

from __future__ import annotations

import re
from pathlib import Path

# Where the compose volumes are mounted in every container that has them.
UPLOADS_ROOT = Path("/data/uploads")
WORKSPACE_ROOT = Path("/data/workspace")

# An ID is opaque and machine-generated: lowercase hex with hyphens, which a
# UUID satisfies. Deliberately narrow -- a dot, a slash or a backslash cannot
# appear, so "..", an absolute path and a Windows drive letter are rejected by
# the shape of the thing rather than by a blocklist of tricks.
DATASET_ID_PATTERN = re.compile(r"^[0-9a-f][0-9a-f-]{7,63}$")

# File names are chosen by the researcher, so they allow more, but still no
# separators and no leading dot.
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class InvalidDatasetId(ValueError):
    """The dataset ID is not the shape an ID is allowed to be."""


class InvalidFilename(ValueError):
    """The file name is not the shape a file name is allowed to be."""


class DatasetNotFound(FileNotFoundError):
    """No dataset with this ID has been uploaded."""


def validate_dataset_id(dataset_id: str) -> str:
    if not isinstance(dataset_id, str) or not DATASET_ID_PATTERN.match(dataset_id):
        raise InvalidDatasetId(
            f"{dataset_id!r} is not a dataset ID. IDs are lowercase hex and "
            "hyphens, 8 to 64 characters."
        )
    return dataset_id


def validate_filename(filename: str) -> str:
    if not isinstance(filename, str) or not FILENAME_PATTERN.match(filename):
        raise InvalidFilename(
            f"{filename!r} is not a file name. Names may not contain path "
            "separators and may not start with a dot."
        )
    return filename


def upload_root(dataset_id: str) -> Path:
    """Where this dataset's uploaded files live. Read-only in every sandbox."""
    return _contained(UPLOADS_ROOT, validate_dataset_id(dataset_id))


def workspace_root(dataset_id: str) -> Path:
    """Where derived files for this dataset go. Writable in the sandboxes."""
    return _contained(WORKSPACE_ROOT, validate_dataset_id(dataset_id))


def resolve_upload(dataset_id: str, filename: str) -> Path:
    """The path of one uploaded file, or an error explaining why not."""
    root = upload_root(dataset_id)
    if not root.is_dir():
        raise DatasetNotFound(f"no dataset {dataset_id!r} has been uploaded")

    path = _contained(root, validate_filename(filename))
    if not path.is_file():
        raise DatasetNotFound(f"dataset {dataset_id!r} has no file {filename!r}")
    return path


def list_dataset_ids() -> list[str]:
    """Every uploaded dataset, ignoring anything not named like an ID."""
    if not UPLOADS_ROOT.is_dir():
        return []
    return sorted(
        entry.name
        for entry in UPLOADS_ROOT.iterdir()
        if entry.is_dir() and DATASET_ID_PATTERN.match(entry.name)
    )


def list_filenames(dataset_id: str) -> list[str]:
    root = upload_root(dataset_id)
    if not root.is_dir():
        raise DatasetNotFound(f"no dataset {dataset_id!r} has been uploaded")
    return sorted(entry.name for entry in root.iterdir() if entry.is_file())


def _contained(root: Path, name: str) -> Path:
    """Join, then prove the result is still inside root.

    The patterns above should make this unreachable. It is here anyway
    because the cost of being wrong about that is another researcher's
    unpublished data, and because a symlink inside the uploads volume would
    escape a pattern check that a resolved-path check catches.
    """
    candidate = (root / name).resolve()
    resolved_root = root.resolve()

    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise InvalidDatasetId(f"{name!r} resolves outside {root}")
    return candidate
