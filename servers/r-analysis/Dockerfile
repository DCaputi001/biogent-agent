# Dockerfile
# Image for the R analysis sandbox: the Seurat/SingleCellExperiment/URD
# adapters from 7.3, and the R-side analysis tools after that.
#
# Two things here are requirements rather than preferences. R is pinned to a
# 4.4.x release because the adapters target Seurat v4/v5 on R >= 4.4.0, and
# package versions come from a committed renv.lock because an analysis whose
# package versions are not recorded is not reproducible -- which is the whole
# claim this service makes in its reports.

FROM rocker/r-ver:4.4.2

# The base image points repos at a dated Posit Package Manager snapshot, so
# these installs resolve to the same versions on every build and, on Linux,
# come down as prebuilt binaries rather than sources.
RUN Rscript -e 'install.packages("renv")'

RUN useradd --system --uid 10001 --user-group biogent

# R resolves "~" on startup and warns when it does not exist. The rootfs is
# read-only at runtime, so point HOME at the writable tmpfs rather than
# creating a home directory R cannot use.
ENV HOME=/tmp

WORKDIR /app

# Restore into the site library rather than a project library: the runtime
# filesystem is read-only, and renv's project autoloader wants to write to the
# project directory on startup.
COPY servers/r-analysis/renv.lock ./renv.lock
RUN Rscript -e 'renv::restore(library = .libPaths()[1], prompt = FALSE)'

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
