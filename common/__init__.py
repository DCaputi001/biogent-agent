# __init__.py
# Marks common/ as a package. Code here is shared by the orchestrator and the
# MCP servers, so it must stay free of dependencies that a sandbox image is not
# allowed to hold -- no model client, no database driver, no cloud SDK.
