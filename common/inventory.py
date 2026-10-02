# inventory.py
# Describes the files of a dataset without interpreting them: name, size,
# checksum, detected container format.
#
# Everything here is safe to run on a file nobody has vouched for -- it reads
# bytes and hashes them, and never deserializes anything. That is what lets
# the data-access server answer "what did the researcher give us" before any
# sandbox opens the file for real.

from __future__ import annotations

import hashlib
from pathlib import Path

from common.datasets import list_filenames, resolve_upload
from common.formats import detect_format

# Hashing is streamed: an uploaded matrix does not fit in memory twice, and
# the whole point of the checksum is that it is taken over the whole file.
_HASH_CHUNK_BYTES = 1024 * 1024


def describe_dataset(dataset_id: str) -> dict[str, object]:
    """Everything known about a dataset from its bytes alone.

    The result deliberately contains no filesystem path. A tool result is
    read by a language model, and a path in one is a path that can be
    repeated back as an argument somewhere else.
    """
    files = [
        describe_file(dataset_id, filename)
        for filename in list_filenames(dataset_id)
    ]
    return {
        "dataset_id": dataset_id,
        "file_count": len(files),
        "files": files,
    }


def describe_file(dataset_id: str, filename: str) -> dict[str, object]:
    path = resolve_upload(dataset_id, filename)
    return {
        "filename": filename,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_of(path),
        # The container format, from the file's first bytes. What is inside it
        # is a question only the sandbox that can open it may answer.
        "format": detect_format(path).value,
    }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
