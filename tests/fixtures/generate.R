# generate.R
# Writes the synthetic SingleCellExperiment fixture, and a deliberately
# truncated copy of it, into the uploads volume. Runs inside the r-analysis
# image; driven by scripts/generate-fixtures.sh.
#
# The values here must match tests/fixtures/spec.py. They are duplicated
# rather than shared because the two generators run in different language
# runtimes; tests/test_fixture_spec.py checks the two copies agree.

suppressPackageStartupMessages(library(SingleCellExperiment))

UPLOADS_ROOT <- "/data/uploads"

RDS_DATASET_ID <- "00000000-0000-4000-8000-000000000002"
MALFORMED_DATASET_ID <- "00000000-0000-4000-8000-000000000003"
RDS_FILENAME <- "fixture.rds"
MALFORMED_FILENAME <- "truncated.rds"

N_CELLS <- 50
N_GENES <- 200
LAYER_NAME <- "counts"
OBS_COLUMN <- "sample_id"
RANDOM_SEED <- 20260930
MALFORMED_PREFIX_BYTES <- 512

set.seed(RANDOM_SEED)

counts <- matrix(
  rpois(N_GENES * N_CELLS, lambda = 2),
  nrow = N_GENES,
  ncol = N_CELLS,
  dimnames = list(
    sprintf("ENSG%08d", seq_len(N_GENES) - 1),
    sprintf("cell%04d", seq_len(N_CELLS) - 1)
  )
)

# SingleCellExperiment is genes x cells, the transpose of AnnData's cells x
# genes. Getting this backwards is the classic single-cell bug, and the
# fixture's unequal dimensions are what make an assertion catch it.
sce <- SingleCellExperiment(
  assays = setNames(list(counts), LAYER_NAME),
  colData = DataFrame(
    sample_id = sprintf("sample%d", (seq_len(N_CELLS) - 1) %% 3),
    row.names = colnames(counts)
  )
)
stopifnot(identical(OBS_COLUMN, "sample_id"))

valid_dir <- file.path(UPLOADS_ROOT, RDS_DATASET_ID)
dir.create(valid_dir, recursive = TRUE, showWarnings = FALSE)
valid_path <- file.path(valid_dir, RDS_FILENAME)
saveRDS(sce, valid_path)
cat(sprintf("wrote %s (%d genes x %d cells)\n", valid_path, N_GENES, N_CELLS))

# The malformed fixture: a real .rds cut short. Its compression and R headers
# survive, so it is still detected as an R object and fails where it matters,
# inside readRDS in the sandbox, rather than being rejected before anything
# opens it.
malformed_dir <- file.path(UPLOADS_ROOT, MALFORMED_DATASET_ID)
dir.create(malformed_dir, recursive = TRUE, showWarnings = FALSE)
malformed_path <- file.path(malformed_dir, MALFORMED_FILENAME)

source_connection <- file(valid_path, "rb")
prefix <- readBin(source_connection, "raw", n = MALFORMED_PREFIX_BYTES)
close(source_connection)

target_connection <- file(malformed_path, "wb")
writeBin(prefix, target_connection)
close(target_connection)
cat(sprintf("wrote %s (%d bytes, deliberately truncated)\n", malformed_path, length(prefix)))
