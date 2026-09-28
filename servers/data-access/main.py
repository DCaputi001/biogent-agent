# main.py
# Entry point for the data access server. Serves the health endpoint until
# Phase 7.3, when this becomes the only component that turns an opaque dataset
# ID into a storage location -- the agent never constructs a path itself.

from common.health import serve

COMPONENT = "data-access"

if __name__ == "__main__":
    serve(COMPONENT)
