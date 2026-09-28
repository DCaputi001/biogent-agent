# lockfile.R
# Declares the R packages this server needs and writes renv.lock from them.
# Run inside the pinned R image by generate-renv-lock.sh, never by hand -- the
# versions it records are the versions of whatever R and CRAN snapshot it ran
# against, so the image is part of the input.
#
# This file is the one place the package list lives. Add a package here, rerun
# the generator, and commit the resulting lockfile alongside this change.

R_PACKAGES <- c(
  # Serves the health endpoint now and the MCP HTTP transport from 7.2.
  "httpuv"
)

# Build in a scratch directory so renv's project files (.Rprofile, renv/) are
# never created in the repo: only the lockfile is an output.
BUILD_DIR <- "/build"
OUTPUT_LOCKFILE <- "/out/renv.lock"

dir.create(BUILD_DIR, showWarnings = FALSE)
setwd(BUILD_DIR)

renv::init(bare = TRUE, restart = FALSE)
renv::install(R_PACKAGES)
renv::snapshot(packages = R_PACKAGES, prompt = FALSE)

file.copy("renv.lock", OUTPUT_LOCKFILE, overwrite = TRUE)
cat("wrote", OUTPUT_LOCKFILE, "\n")
