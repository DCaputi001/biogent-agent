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
  "httr2"
)

# The rocker image pins CRAN to the snapshot current when its R version shipped
# -- 2025-02-27 for R 4.4.2 -- and mcptools did not exist yet at that date. The
# snapshot is therefore chosen here rather than inherited, which also means the
# package set stops moving when the base image is rebuilt.
CRAN_SNAPSHOT <- "https://p3m.dev/cran/__linux__/noble/2026-09-20"

# Build in a scratch directory so renv's project files (.Rprofile, renv/) are
# never created in the repo: only the lockfile is an output.
BUILD_DIR <- "/build"
OUTPUT_LOCKFILE <- "/out/renv.lock"

dir.create(BUILD_DIR, showWarnings = FALSE)
setwd(BUILD_DIR)

# Set before init so the URL is what renv records in the lockfile, and so
# restore() inside the image resolves from the same snapshot.
options(repos = c(CRAN = CRAN_SNAPSHOT))

renv::init(bare = TRUE, restart = FALSE)
renv::install(R_PACKAGES)
renv::snapshot(packages = R_PACKAGES, prompt = FALSE)

file.copy("renv.lock", OUTPUT_LOCKFILE, overwrite = TRUE)
cat("wrote", OUTPUT_LOCKFILE, "\n")
