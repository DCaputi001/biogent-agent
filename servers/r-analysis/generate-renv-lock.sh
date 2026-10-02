#!/usr/bin/env sh
# generate-renv-lock.sh
# Regenerates servers/r-analysis/renv.lock inside the same build environment
# the server image uses, and copies only the lockfile back out.
#
# Run from the repo root after changing the package list in lockfile.R, then
# commit the lockfile with that change. It is a developer step, not a build
# step: the Dockerfile restores from the committed lockfile and never resolves
# versions itself, because a build that picks its own versions is a build
# whose results cannot be reproduced later.

set -eu

SERVER_DIR="servers/r-analysis"
DEPS_IMAGE="biogent-agent-r-deps"

. scripts/host-path.sh

# The Dockerfile's `deps` stage is the single source of truth for the R
# version and the system libraries the packages compile against. Building it
# here means the environment that resolves versions is the environment that
# will install them -- a lockfile generated against a different R or a
# different libcurl is worse than none, because it looks authoritative.
echo "Building the ${DEPS_IMAGE} image from ${SERVER_DIR}/Dockerfile"
docker build \
    --target deps \
    --tag "${DEPS_IMAGE}" \
    --file "${SERVER_DIR}/Dockerfile" \
    .

echo "Generating ${SERVER_DIR}/renv.lock"
docker run --rm \
    --volume "$(host_path "${SERVER_DIR}"):/out" \
    "${DEPS_IMAGE}" \
    Rscript -e 'source("/out/lockfile.R")'

echo "Done. Review the diff and commit renv.lock with the change that caused it."
