# generate.py
# Writes the synthetic AnnData fixture into the uploads volume. Runs inside
# the python-analysis image, where anndata lives; driven by
# scripts/generate-fixtures.sh.
#
# Synthetic on purpose. Real research data belongs to the researcher and never
# enters this repo, and a fixture whose exact dimensions we chose is a better
# test than a real dataset whose properties we would have to look up.

from __future__ import annotations

import sys
from pathlib import Path

import anndata
import numpy as np
import pandas as pd
from scipy import sparse

# spec.py sits next to this file and is mounted into the container with it;
# the container has no notion of the repo, so the directory goes on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from spec import (
    H5AD_DATASET_ID,
    H5AD_FILENAME,
    LAYER_NAME,
    N_CELLS,
    N_GENES,
    OBS_COLUMN,
    RANDOM_SEED,
    VAR_COLUMN,
)

UPLOADS_ROOT = Path("/data/uploads")

# Counts are integers because they are counts. One of 7.3's later validation
# checks is exactly this, so the fixture has to be able to pass it.
_MAX_COUNT = 50
_DENSITY = 0.2


def main() -> None:
    generator = np.random.default_rng(RANDOM_SEED)

    counts = sparse.random(
        N_CELLS,
        N_GENES,
        density=_DENSITY,
        format="csr",
        random_state=generator,
        data_rvs=lambda size: generator.integers(1, _MAX_COUNT, size=size),
        dtype=np.int32,
    )

    adata = anndata.AnnData(
        X=counts,
        obs=pd.DataFrame(
            {OBS_COLUMN: [f"sample{index % 3}" for index in range(N_CELLS)]},
            index=[f"cell{index:04d}" for index in range(N_CELLS)],
        ),
        var=pd.DataFrame(
            {VAR_COLUMN: [f"GENE{index:04d}" for index in range(N_GENES)]},
            index=[f"ENSG{index:08d}" for index in range(N_GENES)],
        ),
    )
    adata.layers[LAYER_NAME] = counts.copy()

    destination = UPLOADS_ROOT / H5AD_DATASET_ID
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / H5AD_FILENAME
    adata.write_h5ad(target)

    print(f"wrote {target} ({N_CELLS} cells x {N_GENES} genes)")


if __name__ == "__main__":
    main()
