"""A dataset reaches a sandbox, is described, and is opened -- safely.

The first slice of Phase 7.3, end to end through the real MCP path: an
opaque ID resolves, a file is described from its bytes, the Python sandbox
reads an AnnData file, and the R sandbox deserializes an R object.

The last of those is the one the whole architecture is built around. readRDS
on a file the researcher supplied is equivalent to running code we did not
write (CVE-2024-27322), so the tests below check not only that a malformed
file fails, but that it fails *inside* the sandbox and leaves the server
answering afterwards.

Requires the compose stack and the generated fixtures:
    sh scripts/generate-fixtures.sh
    docker compose up -d --wait
"""

import pytest

from common.servers import DATA_ACCESS, PYTHON_ANALYSIS, R_ANALYSIS
from tests.fixtures import spec
from tests.ingestion.conftest import call_tool, call_tool_expecting_failure
from tests.isolation.conftest import SANDBOX_SERVICES, exec_in, running_services

pytestmark = pytest.mark.docker

# Ways of asking for a file that is not in the dataset. The resolver must
# refuse all of them, in both runtimes.
TRAVERSAL_FILENAMES = [
    "../../etc/passwd",
    "../fixture.rds",
    "/etc/passwd",
    "..\\fixture.rds",
]

TRAVERSAL_IDS = [
    "../..",
    "/etc",
    "00000000-0000-4000-8000-000000000001/../../etc",
]


def test_datasets_are_listed_by_id() -> None:
    listing = call_tool(DATA_ACCESS, "list_datasets")

    assert spec.H5AD_DATASET_ID in listing["dataset_ids"]
    assert spec.RDS_DATASET_ID in listing["dataset_ids"]


def test_a_dataset_is_described_from_its_bytes() -> None:
    described = call_tool(DATA_ACCESS, "describe", dataset_id=spec.RDS_DATASET_ID)

    assert described["dataset_id"] == spec.RDS_DATASET_ID
    files = {entry["filename"]: entry for entry in described["files"]}
    assert spec.RDS_FILENAME in files

    entry = files[spec.RDS_FILENAME]
    # saveRDS compresses by default, so this also proves detection looks
    # inside the compression rather than stopping at the gzip header.
    assert entry["format"] == "rds"
    assert entry["size_bytes"] > 0
    assert len(entry["sha256"]) == 64


def test_the_h5ad_fixture_is_detected_as_hdf5() -> None:
    described = call_tool(DATA_ACCESS, "describe", dataset_id=spec.H5AD_DATASET_ID)
    entry = next(
        item for item in described["files"] if item["filename"] == spec.H5AD_FILENAME
    )

    assert entry["format"] == "hdf5"


@pytest.mark.parametrize("dataset_id", TRAVERSAL_IDS)
def test_a_traversal_dataset_id_is_refused(dataset_id: str) -> None:
    error = call_tool_expecting_failure(DATA_ACCESS, "describe", dataset_id=dataset_id)
    assert "not a dataset ID" in error, error


@pytest.mark.parametrize("filename", TRAVERSAL_FILENAMES)
def test_a_traversal_filename_is_refused_by_both_runtimes(filename: str) -> None:
    """The Python and R resolvers must agree about what is not a file name."""
    python_error = call_tool_expecting_failure(
        DATA_ACCESS,
        "describe_one_file",
        dataset_id=spec.RDS_DATASET_ID,
        filename=filename,
    )
    assert "not a file name" in python_error, python_error

    r_error = call_tool_expecting_failure(
        R_ANALYSIS,
        "inspect_rds",
        dataset_id=spec.RDS_DATASET_ID,
        filename=filename,
    )
    assert "not a file name" in r_error, r_error


def test_an_unknown_dataset_is_a_clear_error() -> None:
    error = call_tool_expecting_failure(
        DATA_ACCESS,
        "describe",
        dataset_id="00000000-0000-4000-8000-00000000dead",
    )
    assert "has been uploaded" in error, error


def test_the_python_sandbox_summarizes_an_h5ad() -> None:
    summary = call_tool(
        PYTHON_ANALYSIS,
        "summarize_h5ad",
        dataset_id=spec.H5AD_DATASET_ID,
        filename=spec.H5AD_FILENAME,
    )

    assert summary["n_obs"] == spec.N_CELLS
    assert summary["n_vars"] == spec.N_GENES
    assert spec.LAYER_NAME in summary["layers"]
    assert spec.OBS_COLUMN in summary["obs_columns"]
    assert spec.VAR_COLUMN in summary["var_columns"]


def test_the_r_sandbox_inspects_an_rds() -> None:
    inspected = call_tool(
        R_ANALYSIS,
        "inspect_rds",
        dataset_id=spec.RDS_DATASET_ID,
        filename=spec.RDS_FILENAME,
    )

    assert "SingleCellExperiment" in inspected["class"]
    assert spec.LAYER_NAME in inspected["assay_names"]

    # SingleCellExperiment is genes x cells, the transpose of AnnData's
    # cells x genes. The fixture's dimensions differ, so a transposed read
    # cannot pass this.
    assert inspected["dimensions"] == [spec.N_GENES, spec.N_CELLS]


def test_a_malformed_rds_fails_inside_the_sandbox() -> None:
    """The checkpoint case: a truncated R object must not take the server out."""
    error = call_tool_expecting_failure(
        R_ANALYSIS,
        "inspect_rds",
        dataset_id=spec.MALFORMED_DATASET_ID,
        filename=spec.MALFORMED_FILENAME,
    )

    assert spec.MALFORMED_FILENAME in error, (
        f"the error does not name the file that failed: {error}"
    )
    assert "could not be read as an R object" in error, error


def test_the_r_server_still_answers_after_a_malformed_file() -> None:
    """Runs after the malformed call: a bad upload is not a denial of service."""
    assert R_ANALYSIS in running_services()

    inspected = call_tool(
        R_ANALYSIS,
        "inspect_rds",
        dataset_id=spec.RDS_DATASET_ID,
        filename=spec.RDS_FILENAME,
    )
    assert "SingleCellExperiment" in inspected["class"]


@pytest.mark.parametrize("service", SANDBOX_SERVICES)
def test_a_sandbox_cannot_modify_an_upload(service: str) -> None:
    """The original file is evidence. Nothing that analyses it may change it."""
    target = f"/data/uploads/{spec.RDS_DATASET_ID}/tampered"
    result = exec_in(service, "sh", "-c", f"echo x > {target}", timeout=60)

    assert result.returncode != 0, (
        f"{service} wrote into the uploads volume. Uploads are mounted "
        "read-only in every sandbox."
    )
    assert "read-only" in result.output.lower(), result.output.strip()


def test_no_tool_result_contains_a_filesystem_path() -> None:
    """The agent must never be handed a path it could repeat back as input.

    DESIGN.md, "the agent never constructs a file path": the defence is that
    nothing path-shaped is ever in scope, which only holds if results do not
    leak one.
    """
    results = [
        call_tool(DATA_ACCESS, "list_datasets"),
        call_tool(DATA_ACCESS, "describe", dataset_id=spec.H5AD_DATASET_ID),
        call_tool(
            PYTHON_ANALYSIS,
            "summarize_h5ad",
            dataset_id=spec.H5AD_DATASET_ID,
            filename=spec.H5AD_FILENAME,
        ),
        call_tool(
            R_ANALYSIS,
            "inspect_rds",
            dataset_id=spec.RDS_DATASET_ID,
            filename=spec.RDS_FILENAME,
        ),
    ]

    for result in results:
        rendered = repr(result)
        assert "/data/uploads" not in rendered, rendered
        assert "/data/workspace" not in rendered, rendered
