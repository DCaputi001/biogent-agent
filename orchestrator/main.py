# main.py
# Entry point for the orchestrator container. Serves the health endpoint and
# nothing else for now; the LangGraph graph and the API surface described in
# INTEGRATION_CONTRACT.md land in later sub-phases.

from common.health import serve

COMPONENT = "orchestrator"

if __name__ == "__main__":
    serve(COMPONENT)
