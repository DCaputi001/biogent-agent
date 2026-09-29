# healthcheck.R
# Container healthcheck for the R server. Exits 0 when the MCP endpoint answers
# an initialize request, non-zero otherwise.
#
# The Python servers answer a plain GET /healthz next to /mcp; mcptools serves
# the MCP endpoint alone, so this speaks the protocol instead. Checking the
# handshake rather than the open port is the difference between "the process is
# alive" and "the server can take a tool call".

suppressPackageStartupMessages(library(httr2))

ENDPOINT <- "http://127.0.0.1:8000/mcp"

# The lowest protocol version mcptools accepts is not our concern here: an
# unsupported version still proves the endpoint is handling JSON-RPC. Any
# well-formed answer counts as healthy.
initialize_request <- list(
  jsonrpc = "2.0",
  id = 1,
  method = "initialize",
  params = list(
    protocolVersion = "2025-06-18",
    capabilities = structure(list(), names = character(0)),
    clientInfo = list(name = "healthcheck", version = "1")
  )
)

response <- tryCatch(
  request(ENDPOINT) |>
    req_headers(Accept = "application/json, text/event-stream") |>
    req_body_json(initialize_request) |>
    req_timeout(5) |>
    req_error(is_error = function(resp) FALSE) |>
    req_perform(),
  error = function(e) NULL
)

if (is.null(response) || resp_status(response) >= 400) {
  quit(status = 1)
}

quit(status = 0)
