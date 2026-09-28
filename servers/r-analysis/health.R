# health.R
# Entry point for the R analysis sandbox. Serves the same /healthz contract as
# the Python components until Phase 7.2 puts an MCP server on this port.
#
# This is the container that will open uploaded .rds files (7.3), which is why
# it is the most tightly confined of the four: an uploaded R object is
# untrusted code (CVE-2024-27322). See DESIGN.md.

library(httpuv)

COMPONENT <- "r-analysis"
HEALTH_PATH <- "/healthz"

# Matches DEFAULT_PORT in common/health.py. Every component listens on the same
# port so the compose wiring and the healthchecks stay uniform.
PORT <- 8000

json_response <- function(status, body) {
  list(
    status = status,
    headers = list("Content-Type" = "application/json"),
    body = body
  )
}

handle_request <- function(request) {
  if (!identical(request$PATH_INFO, HEALTH_PATH)) {
    return(json_response(404L, '{"error": "not found"}'))
  }
  json_response(200L, sprintf('{"status": "ok", "component": "%s"}', COMPONENT))
}

cat(sprintf("%s listening on 0.0.0.0:%d%s\n", COMPONENT, PORT, HEALTH_PATH))
flush(stdout())

httpuv::runServer("0.0.0.0", PORT, list(call = handle_request))
