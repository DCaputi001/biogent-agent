# h5ad.py
# Reads an AnnData file and reports its shape and structure. The first thing
# biogent does with a dataset, and the only .h5ad code in this slice.
#
# It lives in common/ rather than beside the python-analysis server because
# run_with_timeout executes tool bodies in a spawned child that re-imports the
# function by module path, and "servers/python-analysis" is not an importable
# module name. Only the python-analysis image installs anndata, so only that
# server imports this.
#
# Backed mode throughout: an uploaded matrix can be larger than the sandbox's
# memory limit, and reporting a dataset's shape should not require holding it.

from __future__ import annotations

from common.datasets import resolve_upload

# Column names are reported, not values. A summary is for deciding what to do
# next, and cell barcodes or donor identifiers are the researcher's data, not
# metadata about it.
_MAX_REPORTED_COLUMNS = 50


def summarize(dataset_id: str, filename: str) -> dict[str, object]:
    """Describe the structure of an AnnData file without loading its matrix."""
    import anndata

    path = resolve_upload(dataset_id, filename)

    try:
        adata = anndata.read_h5ad(path, backed="r")
    except Exception as error:
        # anndata raises a variety of types for a file that is not AnnData;
        # what the caller needs is which file and what went wrong, not the
        # class name of an h5py exception.
        raise ValueError(
            f"{filename!r} could not be read as an AnnData file: "
            f"{type(error).__name__}: {error}"
        ) from error

    try:
        return {
            "dataset_id": dataset_id,
            "filename": filename,
            "n_obs": int(adata.n_obs),
            "n_vars": int(adata.n_vars),
            "layers": _names(adata.layers.keys()),
            "obs_columns": _names(adata.obs.columns),
            "var_columns": _names(adata.var.columns),
            "obsm_keys": _names(adata.obsm.keys()),
            "raw_present": adata.raw is not None,
            "x_dtype": str(adata.X.dtype) if adata.X is not None else None,
        }
    finally:
        if adata.isbacked:
            adata.file.close()


def _names(values: object) -> list[str]:
    """Sorted names, with unnamed entries dropped.

    A backed AnnData's layers and obsm can yield a None among their keys, so
    sorting the raw sequence raises on the comparison. Dropping the unnamed
    entry is right for a summary: a caller cannot ask for a layer with no
    name anyway.
    """
    names = sorted(str(value) for value in values if value is not None)
    return names[:_MAX_REPORTED_COLUMNS]
