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

WORKDIR /app

# Restore into the site library rather than a project library: the runtime
# filesystem is read-only, and renv's project autoloader wants to write to the
# project directory on startup.
COPY servers/r-analysis/renv.lock ./renv.lock
RUN Rscript -e 'renv::restore(library = .libPaths()[1], prompt = FALSE)'

COPY servers/r-analysis/health.R ./health.R

USER biogent

EXPOSE 8000

# No curl in the base image, and R is already here.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD ["Rscript", "-e", "if (!grepl('\"status\": \"ok\"', paste(readLines(url('http://127.0.0.1:8000/healthz'), warn = FALSE), collapse = ''))) quit(status = 1)"]

CMD ["Rscript", "health.R"]
