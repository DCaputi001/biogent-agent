# main.R
# The R analysis sandbox, as an MCP server. Holds the
# Seurat/SingleCellExperiment/URD adapters from 7.3 and the R-side analysis
# tools after that; for now it holds the runtime report.
#
# This is the container that opens uploaded .rds files, which is why it is the
# most tightly confined of the four: an uploaded R object is untrusted code
# (CVE-2024-27322). See DESIGN.md.

library(mcptools)

COMPONENT <- "r-analysis"
PORT <- 8000

# Must match TOOL_TIMEOUT_SECONDS in common/tooling.py. R has no equivalent of
# killing a child process from inside the server loop, so this is setTimeLimit:
# it interrupts at the next time R checks, which covers R-level loops but not a
# compiled routine that never yields. The container's CPU and memory limits are
# the backstop for that case.
TOOL_TIMEOUT_SECONDS <- 30

# The R counterpart of common/mcp_app.py's run_tool: every tool body goes
# through it.
#
# The limit must be cleared on the way out. setTimeLimit applies to the current
# top-level computation, and inside an event-loop server that computation is
# the server's own callback loop -- a limit left set does not expire with the
# tool, it expires *on the server*, which then exits. That is not theoretical:
# it killed this container 30 seconds after the first tool call before the
# on.exit below was added.
run_tool <- function(body) {
  setTimeLimit(elapsed = TOOL_TIMEOUT_SECONDS, transient = FALSE)
  on.exit(setTimeLimit(cpu = Inf, elapsed = Inf), add = TRUE)
  body()
}

# Packages whose versions belong in a methods section. The Seurat stack joins
# this list as the adapters land.
REPORTED_PACKAGES <- c("mcptools", "httpuv", "jsonlite")

package_versions <- function(packages) {
  versions <- vapply(packages, function(p) as.character(utils::packageVersion(p)), character(1))
  as.list(versions)
}

runtime_versions_impl <- function() {
  run_tool(function() {
    # Returned as JSON text so that an R tool result and a Python tool result
    # look the same to the orchestrator, which parses one shape.
    jsonlite::toJSON(
      list(
        component = COMPONENT,
        language = "r",
        language_version = paste(R.version$major, R.version$minor, sep = "."),
        implementation = R.version.string,
        packages = package_versions(REPORTED_PACKAGES)
      ),
      auto_unbox = TRUE
    )
  })
}

runtime_versions <- ellmer::tool(
  runtime_versions_impl,
  description = "Report the R version and analysis package versions in use.",
  name = "runtime_versions"
)

cat(sprintf("%s starting MCP server on 0.0.0.0:%d\n", COMPONENT, PORT))
flush(stdout())

# session_tools = FALSE: the default exposes list_r_sessions and
# select_r_session, which let a caller route tool calls into an interactive R
# session over a local socket. That is a developer convenience and, in a
# container whose job is to open untrusted files, an extra door.
mcp_server(
  tools = list(runtime_versions),
  type = "http",
  host = "0.0.0.0",
  port = PORT,
  session_tools = FALSE
)
