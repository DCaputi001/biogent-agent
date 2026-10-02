#!/usr/bin/env sh
# generate-fixtures.sh
# Writes the synthetic test datasets into data/uploads/, using the component
# images so that each fixture is produced by the same stack that will read it.
#
# Run from the repo root before the ingestion tests. Cheap and idempotent:
# both generators are seeded, so rerunning produces the same bytes.
#
# The fixtures are never committed -- .gitignore bans *.h5ad and *.rds
# everywhere, which is what keeps a real researcher dataset out of git. That
# is also why this script exists rather than a folder of checked-in files.
#
# Note the mount is writable here, while docker-compose.yml mounts the same
# directory read-only into every sandbox. Generating fixtures is a developer
# action on the host; a sandbox writing to the uploads volume is not a thing
# that should be possible at all.

set -eu

UPLOADS_DIR="data/uploads"
PYTHON_IMAGE="biogent-agent-python-analysis"
R_IMAGE="biogent-agent-r-analysis"
FIXTURES_DIR="tests/fixtures"

. scripts/host-path.sh

mkdir -p "${UPLOADS_DIR}" data/workspace

if ! docker image inspect "${PYTHON_IMAGE}" >/dev/null 2>&1 ||
    ! docker image inspect "${R_IMAGE}" >/dev/null 2>&1; then
    echo "Component images missing. Run: docker compose build" >&2
    exit 1
fi

UPLOADS_HOST_PATH="$(host_path "${UPLOADS_DIR}")"
FIXTURES_HOST_PATH="$(host_path "${FIXTURES_DIR}")"

echo "Generating the AnnData fixture"
docker run --rm \
    --volume "${UPLOADS_HOST_PATH}:/data/uploads" \
    --volume "${FIXTURES_HOST_PATH}:/fixtures:ro" \
    "${PYTHON_IMAGE}" \
    python /fixtures/generate.py

echo "Generating the SingleCellExperiment and malformed fixtures"
docker run --rm \
    --volume "${UPLOADS_HOST_PATH}:/data/uploads" \
    --volume "${FIXTURES_HOST_PATH}:/fixtures:ro" \
    "${R_IMAGE}" \
    Rscript /fixtures/generate.R

echo "Done. ${UPLOADS_DIR}/ now holds the fixtures the ingestion tests expect."
