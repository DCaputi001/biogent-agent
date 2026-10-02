# formats.py
# Identifies a file from its first bytes. Used by the data-access server to
# describe an upload before anything opens it.
#
# From content, never from the extension. A researcher's ".rds" that is
# actually HDF5 is a mistake worth catching; a hostile ".csv" that is actually
# a serialized R object is the case the whole sandbox exists for, and an
# extension is exactly what an attacker controls.
#
# Detection here is cheap and deliberately shallow: it names the container
# format, not what is inside it. Only the sandbox that can open the file --
# python-analysis for AnnData, r-analysis for R objects -- can say what it
# actually holds, and this module has no scientific dependencies so that
# data-access does not need them either.

from __future__ import annotations

import bz2
import gzip
import lzma
from enum import Enum
from pathlib import Path

# What a decompressor raises when handed a stream that is not what it claims,
# or one that stops early. gzip and bz2 raise OSError subclasses; a stream cut
# mid-member raises EOFError; lzma has its own type.
_BROKEN_STREAM_ERRORS = (OSError, EOFError, lzma.LZMAError)


class FileFormat(str, Enum):
    """The container format of a file, as far as its first bytes show."""

    HDF5 = "hdf5"
    RDS = "rds"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    XZ = "xz"
    TEXT = "text"
    UNKNOWN = "unknown"


# How many bytes any signature below needs, plus room for the R header that
# follows a compression header.
_PREFIX_BYTES = 16

# The HDF5 signature, which is what an .h5ad file starts with.
_HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"

_GZIP_MAGIC = b"\x1f\x8b"
_BZIP2_MAGIC = b"BZh"
_XZ_MAGIC = b"\xfd7zXZ\x00"

# An uncompressed RDS begins with a two-character serialization mode -- "X\n"
# for XDR binary, "A\n" for ASCII, "B\n" for native binary -- and RDS version
# 3 files begin with "RDX3\n". saveRDS() compresses by default, so most real
# files are one of the compressed cases handled below.
_RDS_MODES = (b"X\n", b"A\n", b"B\n")
_RDS_VERSION_3 = b"RDX3\n"


def detect_format(path: Path) -> FileFormat:
    """Identify a file from its leading bytes."""
    with path.open("rb") as handle:
        prefix = handle.read(_PREFIX_BYTES)

    return identify(prefix, path)


def identify(prefix: bytes, path: Path | None = None) -> FileFormat:
    """Identify a format from a file's first bytes.

    Split from detect_format so the signature table can be tested without
    writing files.
    """
    if prefix.startswith(_HDF5_MAGIC):
        return FileFormat.HDF5

    if _is_rds_header(prefix):
        return FileFormat.RDS

    # A compressed file may or may not be an R object; the only way to know is
    # to look past the compression header, which needs the file itself.
    if prefix.startswith(_GZIP_MAGIC):
        return _inside_compression(path, FileFormat.GZIP)
    if prefix.startswith(_BZIP2_MAGIC):
        return _inside_compression(path, FileFormat.BZIP2)
    if prefix.startswith(_XZ_MAGIC):
        return _inside_compression(path, FileFormat.XZ)

    if prefix and _looks_like_text(prefix):
        return FileFormat.TEXT

    return FileFormat.UNKNOWN


def _is_rds_header(prefix: bytes) -> bool:
    return prefix.startswith(_RDS_VERSION_3) or prefix.startswith(_RDS_MODES)


def _inside_compression(path: Path | None, compression: FileFormat) -> FileFormat:
    """Decompress just enough to see whether an R object is in there.

    Returns the compression format itself when the contents are something
    else, or when the stream cannot be read -- a corrupt archive is a real
    answer about a file, and raising here would turn "describe this upload"
    into an error for a file the researcher may want to hear about.
    """
    if path is None:
        return compression

    openers = {
        FileFormat.GZIP: gzip.open,
        FileFormat.BZIP2: bz2.open,
        FileFormat.XZ: lzma.open,
    }

    try:
        with openers[compression](path, "rb") as stream:
            inner = stream.read(_PREFIX_BYTES)
    except _BROKEN_STREAM_ERRORS:
        return compression

    return FileFormat.RDS if _is_rds_header(inner) else compression


def _looks_like_text(prefix: bytes) -> bool:
    try:
        prefix.decode("utf-8")
    except UnicodeDecodeError:
        # A truncated multi-byte character at the read boundary is not
        # evidence of binary content, but anything else is.
        return False
    return b"\x00" not in prefix
