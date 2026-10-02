# main.py
# The data access server, as an MCP server. The only component that turns an
# opaque dataset ID into a storage location -- the agent asks for a dataset by
# ID and never sees, or constructs, a path.
#
# Locally an ID resolves to a folder under the uploads volume. After the
# import it resolves to a user-scoped S3 prefix, and the agent cannot tell the
# difference, which is the point. See INTEGRATION_CONTRACT.md section 3.

from mcp.server import MCPServer

from common.datasets import list_dataset_ids
from common.inventory import describe_dataset, describe_file
from common.mcp_app import run_server, run_tool
from common.runtime import runtime_report
from common.servers import DATA_ACCESS

REPORTED_PACKAGES = ("mcp", "uvicorn")


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def runtime_versions() -> dict[str, object]:
        """Report the Python version and package versions in use."""
        return run_tool(runtime_report, DATA_ACCESS, REPORTED_PACKAGES)

    @server.tool()
    def list_datasets() -> dict[str, object]:
        """List the IDs of every uploaded dataset."""
        return run_tool(_list_datasets)

    @server.tool()
    def describe(dataset_id: str) -> dict[str, object]:
        """Describe a dataset's files: name, size, checksum, detected format.

        Reads bytes only. Nothing here deserializes a file, so it is safe to
        call on an upload nobody has vouched for yet.
        """
        return run_tool(describe_dataset, dataset_id)

    @server.tool()
    def describe_one_file(dataset_id: str, filename: str) -> dict[str, object]:
        """Describe a single file in a dataset."""
        return run_tool(describe_file, dataset_id, filename)


def _list_datasets() -> dict[str, object]:
    ids = list_dataset_ids()
    return {"dataset_ids": ids, "count": len(ids)}


if __name__ == "__main__":
    run_server(DATA_ACCESS, register_tools)
