#!/usr/bin/env sh
# generate-renv-lock.sh
# Regenerates servers/r-analysis/renv.lock inside the same R image the server
# is built from, and copies only the lockfile back out.
#
# Run from the repo root after changing the package list in lockfile.R, then
# commit the lockfile with that change. It is a developer step, not a build
# step: the Dockerfile restores from the committed lockfile and never resolves
# versions itself, because a build that picks its own versions is a build whose
# results cannot be reproduced later.

set -eu

SERVER_DIR="servers/r-analysis"

# Single source of truth for the R version: the Dockerfile's base image. A
# lockfile generated against a different R than the image runs is worse than
# no lockfile, because it looks authoritative.
R_IMAGE=$(awk '/^FROM /{print $2; exit}' "${SERVER_DIR}/Dockerfile")

# Git Bash rewrites arguments that look like absolute POSIX paths, which turns
# the container-side /out into C:/Program Files/Git/out and leaves the mount
# pointing at nothing. cygpath gives docker the host path in the form Windows
# wants; MSYS_NO_PATHCONV leaves the container-side paths alone.
HOST_DIR="$(pwd)/${SERVER_DIR}"
if command -v cygpath >/dev/null 2>&1; then
    HOST_DIR=$(cygpath --windows "${HOST_DIR}")
    MSYS_NO_PATHCONV=1
    MSYS2_ARG_CONV_EXCL='*'
    export MSYS_NO_PATHCONV MSYS2_ARG_CONV_EXCL
fi

echo "Generating ${SERVER_DIR}/renv.lock using ${R_IMAGE}"

docker run --rm \
    --volume "${HOST_DIR}:/out" \
    "${R_IMAGE}" \
    Rscript -e 'install.packages("renv"); source("/out/lockfile.R")'

echo "Done. Review the diff and commit renv.lock with the change that caused it."
