# lockfile.R
# Declares the R packages this server needs and writes renv.lock from them.
# Run inside the pinned R image by generate-renv-lock.sh, never by hand -- the
# versions it records are the versions of whatever R and CRAN snapshot it ran
# against, so the image is part of the input.
#
# This file is the one place the package list lives. Add a package here, rerun
# the generator, and commit the resulting lockfile alongside this change.

R_PACKAGES <- c(
  # The MCP server itself: mcp_server(type = "http") speaks Streamable HTTP,
  # which the Python SDK's client talks to (verified before this was adopted).
  # Brings ellmer, httr2, nanonext, openssl and processx with it.
  "mcptools",
  # Used directly by the server and the healthcheck.
  "httpuv",
  "jsonlite",
  "httr2",
  # The container structure every .rds adapter converts through, and the
  # writer that turns it into the .h5ad the Python tools read.
  #
  # anndataR rather than zellkonverter, which is what the build plan named:
  # zellkonverter converts through reticulate and basilisk, which means a
  # conda Python environment inside the container that has no network and a
  # read-only filesystem. anndataR reads and writes .h5ad natively in R. It is
  # the reason this image needs R >= 4.5. See DESIGN.md.
  "bioc::SingleCellExperiment",
  "bioc::anndataR"
)

# The rocker image pins CRAN to the snapshot current when its R version shipped
# -- and mcptools, released 2026-09-18, is newer than any of those snapshots.
# The snapshot is therefore chosen here rather than inherited, which also means
# the package set stops moving when the base image is rebuilt.
CRAN_SNAPSHOT <- "https://p3m.dev/cran/__linux__/noble/2026-09-20"

# Bioconductor releases are tied to an R version: 3.23 goes with R 4.6, which
# is what servers/r-analysis/Dockerfile pins. Naming it here rather than
# letting renv infer it keeps the two from drifting apart silently.
BIOCONDUCTOR_VERSION <- "3.23"

# Build in a scratch directory so renv's project files (.Rprofile, renv/) are
# never created in the repo: only the lockfile is an output.
BUILD_DIR <- "/build"
OUTPUT_LOCKFILE <- "/out/renv.lock"

dir.create(BUILD_DIR, showWarnings = FALSE)
setwd(BUILD_DIR)

# Set before init so the URLs are what renv records in the lockfile, and so
# restore() inside the image resolves from the same snapshot.
options(repos = c(CRAN = CRAN_SNAPSHOT))
options(renv.config.bioconductor.version = BIOCONDUCTOR_VERSION)

renv::init(bare = TRUE, bioconductor = BIOCONDUCTOR_VERSION, restart = FALSE)
renv::install(R_PACKAGES)

# snapshot() takes plain names; the bioc:: prefix is an install-time
# instruction, not part of the package name it records.
renv::snapshot(packages = sub("^bioc::", "", R_PACKAGES), prompt = FALSE)

file.copy("renv.lock", OUTPUT_LOCKFILE, overwrite = TRUE)
cat("wrote", OUTPUT_LOCKFILE, "\n")
