# health.py
# Dependency-free HTTP health endpoint shared by every Python component of this
# service. Exposes serve(), which blocks; each component's main.py is a thin
# wrapper around it.
#
# This is deliberately the whole of what a container runs in Phase 7.1. The MCP
# application replaces the handler on the same port and network in 7.2, so the
# compose wiring, the network boundary and the healthchecks are all proven
# before any tool exists to call.

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HEALTH_PATH = "/healthz"

# Every component listens on the same port. Only the orchestrator publishes it
# to the host; the servers are reachable on the internal compose network only.
DEFAULT_PORT = 8000

# Binding to a specific interface inside a container gains nothing -- the
# container's network namespace is the boundary, and the compose network is
# what makes it internal.
BIND_HOST = "0.0.0.0"


def _build_handler(component: str) -> type[BaseHTTPRequestHandler]:
    """Create a handler class bound to one component name.

    BaseHTTPRequestHandler is instantiated per request by HTTPServer, so the
    component name cannot be passed as a constructor argument. A class built
    per server is the least surprising way to close over it.
    """

    class HealthRequestHandler(BaseHTTPRequestHandler):
        # Default is HTTP/1.0, which closes the connection after every
        # response. Docker healthchecks poll often enough for that to matter.
        protocol_version = "HTTP/1.1"

        # Method name is fixed by BaseHTTPRequestHandler's dispatch.
        def do_GET(self) -> None:
            if self.path != HEALTH_PATH:
                self._respond(404, {"error": "not found", "path": self.path})
                return
            self._respond(200, {"status": "ok", "component": component})

        def _respond(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            # The default writes to stderr, which makes a successful
            # healthcheck look like an error in `docker compose logs`.
            sys.stdout.write(f"{component} {self.address_string()} {format % args}\n")
            sys.stdout.flush()

    return HealthRequestHandler


def serve(component: str, port: int = DEFAULT_PORT) -> None:
    """Serve the health endpoint until the process is stopped."""
    server = HTTPServer((BIND_HOST, port), _build_handler(component))
    print(f"{component} listening on {BIND_HOST}:{port}{HEALTH_PATH}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Compose sends SIGTERM on `down`; SIGINT arrives when a developer
        # runs the stack in the foreground. Neither is a failure.
        print(f"{component} shutting down", flush=True)
    finally:
        server.server_close()
