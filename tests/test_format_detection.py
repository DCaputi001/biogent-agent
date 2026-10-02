"""A file is what its bytes say it is, not what its name says.

The extension is the one piece of metadata an attacker fully controls, and
this service opens uploaded R objects, where being wrong about the format
means deserializing something in a runtime that executes it
(CVE-2024-27322). common/formats.py therefore reads the signature.

The R cases matter most: saveRDS() compresses by default, so a real .rds is
usually a gzip stream with the R header inside it, and a detector that only
knows the uncompressed header would call almost every real file "gzip".
"""

import bz2
import gzip
import lzma
from pathlib import Path

import pytest

from common.formats import FileFormat, detect_format, identify

HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"

# An uncompressed RDS in XDR mode, and the version-3 header.
RDS_XDR = b"X\n\x00\x00\x00\x03"
RDS_V3 = b"RDX3\nX\n\x00\x00\x00\x03"

COMPRESSORS = {
    "gzip": (gzip.compress, FileFormat.GZIP),
    "bzip2": (bz2.compress, FileFormat.BZIP2),
    "xz": (lzma.compress, FileFormat.XZ),
}


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        (HDF5_MAGIC + b"\x00" * 8, FileFormat.HDF5),
        (RDS_XDR, FileFormat.RDS),
        (RDS_V3, FileFormat.RDS),
        (b"A\n2\n", FileFormat.RDS),
        (b"gene,cell,count\n", FileFormat.TEXT),
        (b"\x00\x01\x02\x03binary", FileFormat.UNKNOWN),
        (b"", FileFormat.UNKNOWN),
    ],
)
def test_signatures_are_identified(prefix: bytes, expected: FileFormat) -> None:
    assert identify(prefix) is expected


@pytest.mark.parametrize("name", sorted(COMPRESSORS))
def test_a_compressed_r_object_is_still_an_r_object(
    name: str, tmp_path: Path
) -> None:
    """The common case: saveRDS() compresses, so the R header is inside."""
    compress, _ = COMPRESSORS[name]
    path = tmp_path / f"object.{name}"
    path.write_bytes(compress(RDS_XDR + b"payload" * 100))

    assert detect_format(path) is FileFormat.RDS


@pytest.mark.parametrize("name", sorted(COMPRESSORS))
def test_a_compressed_non_r_file_reports_its_compression(
    name: str, tmp_path: Path
) -> None:
    compress, expected = COMPRESSORS[name]
    path = tmp_path / f"archive.{name}"
    path.write_bytes(compress(b"just some text, not an R object"))

    assert detect_format(path) is expected


def test_an_extension_never_decides(tmp_path: Path) -> None:
    """The case the sandbox exists for: a hostile name over real bytes."""
    disguised = tmp_path / "harmless.csv"
    disguised.write_bytes(gzip.compress(RDS_XDR + b"payload"))

    assert detect_format(disguised) is FileFormat.RDS

    mislabelled = tmp_path / "data.rds"
    mislabelled.write_bytes(HDF5_MAGIC + b"\x00" * 64)

    assert detect_format(mislabelled) is FileFormat.HDF5


def test_a_corrupt_archive_is_described_not_raised(tmp_path: Path) -> None:
    """Describing an upload must work even when the upload is broken."""
    truncated = tmp_path / "truncated.gz"
    truncated.write_bytes(gzip.compress(RDS_XDR + b"payload" * 100)[:20])

    assert detect_format(truncated) is FileFormat.GZIP
