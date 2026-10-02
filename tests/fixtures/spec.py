# spec.py
# What the generated fixtures are: their dataset IDs, file names and exact
# dimensions. Imported by the generators that write them and by the tests that
# assert on them, so neither can drift from the other.
#
# Fixtures are generated, never committed: .gitignore bans *.h5ad and *.rds
# everywhere, and that ban is what stops a real researcher dataset being
# committed by accident. An exception carved out for tests/ would be a hole in
# exactly the place someone would drop a real file into.

# Dataset IDs are fixed rather than random so a failing test names a dataset
# that can be inspected afterwards. They are valid UUIDs, matching the shape
# DATASET_ID_PATTERN allows in common/datasets.py.
H5AD_DATASET_ID = "00000000-0000-4000-8000-000000000001"
RDS_DATASET_ID = "00000000-0000-4000-8000-000000000002"
MALFORMED_DATASET_ID = "00000000-0000-4000-8000-000000000003"

H5AD_FILENAME = "fixture.h5ad"
RDS_FILENAME = "fixture.rds"
MALFORMED_FILENAME = "truncated.rds"

# Small enough to generate in under a second, large enough that a transposed
# matrix is obvious: the counts differ, so an assertion on them cannot pass by
# coincidence.
N_CELLS = 50
N_GENES = 200

# Recorded in the fixtures and asserted on, so a summary that silently loses a
# layer or a column fails.
LAYER_NAME = "counts"
OBS_COLUMN = "sample_id"
VAR_COLUMN = "gene_symbol"

# Every generator seeds with this. A fixture that changes between runs turns a
# real regression into noise.
RANDOM_SEED = 20260930

# How much of the valid .rds the malformed fixture keeps. Enough to leave the
# compression and R headers intact, so the file is still detected as an R
# object and fails at deserialization rather than at detection -- which is the
# failure path worth testing.
MALFORMED_PREFIX_BYTES = 512
