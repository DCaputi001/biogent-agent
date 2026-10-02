# Dockerfile
# Image for the R analysis sandbox: the Seurat/SingleCellExperiment/URD
# adapters from 7.3, and the R-side analysis tools after that.
#
# Two things here are requirements rather than preferences. R is pinned to a
# 4.6.x release -- above the plan's R >= 4.4.0 floor because anndataR, which
# writes the .h5ad the Python tools read, needs R >= 4.5 and Bioconductor
# 3.23. Package versions come from a committed renv.lock because an analysis
# whose package versions are not recorded is not reproducible, which is the
# whole claim this service makes in its reports.
#
# Built in stages because Bioconductor publishes no Linux binaries, so the
# packages compile from source. The development headers, the apt lists and
# curl stay in the build stages; the runtime image gets the finished library
# and nothing else.
#
# Note what this does NOT do: rocker/r-ver ships a compiler in the base image,
# so the runtime still has gcc. Removing it is a separate piece of hardening
# against a slimmer base, worth doing before this service sees a real
# uploaded file from outside a pilot.

# --- deps: the build environment, and nothing that depends on renv.lock ------
# generate-renv-lock.sh builds this target and generates the lockfile inside
# it, so the environment that resolves versions is the one that installs them.
FROM rocker/r-ver:4.6.1 AS deps

# System libraries the Bioconductor and CRAN sources link against. Headers
# only matter here; the shared libraries they belong to are already in the
# base image, which is why the runtime stage needs no apt at all.
#   zlib1g-dev  XVector, and anything that touches compressed streams
#   libssl-dev, libcurl4-openssl-dev  openssl and curl, pulled in by mcptools
#   libxml2-dev  XML-handling dependencies in the Bioconductor stack
# curl itself is a runtime requirement of renv's downloader and is absent from
# this base image, unlike 4.4.x.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN Rscript -e 'install.packages("renv")'

# --- builder: the package library, built from the committed lockfile ---------
FROM deps AS builder

WORKDIR /build

# Restore into the site library rather than a project library: the runtime
# filesystem is read-only, and renv's project autoloader wants to write to the
# project directory on startup.
COPY servers/r-analysis/renv.lock ./renv.lock
RUN Rscript -e 'renv::restore(library = .libPaths()[1], prompt = FALSE)'

# --- runtime: no compiler, no package manager, no build headers --------------
FROM rocker/r-ver:4.6.1 AS runtime

RUN useradd --system --uid 10001 --user-group biogent

# R resolves "~" on startup and warns when it does not exist. The rootfs is
# read-only at runtime, so point HOME at the writable tmpfs rather than
# creating a home directory R cannot use.
ENV HOME=/tmp

COPY --from=builder /usr/local/lib/R/site-library /usr/local/lib/R/site-library

WORKDIR /app

COPY servers/r-analysis/datasets.R ./datasets.R
COPY servers/r-analysis/main.R ./main.R
COPY servers/r-analysis/healthcheck.R ./healthcheck.R

USER biogent

EXPOSE 8000

# Speaks MCP rather than checking an open port: mcptools serves /mcp only, and
# a listening socket does not prove the server can take a tool call. Slower to
# start than the Python servers' GET /healthz, hence the longer start period --
# R has a package library to load.
HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=5 \
    CMD ["Rscript", "healthcheck.R"]

CMD ["Rscript", "main.R"]
