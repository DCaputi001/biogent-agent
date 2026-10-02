# main.R
# The R analysis sandbox, as an MCP server. Holds the
# Seurat/SingleCellExperiment/URD adapters from 7.3 and the R-side analysis
# tools after that; for now it holds the runtime report.
#
# This is the container that opens uploaded .rds files, which is why it is the
# most tightly confined of the four: an uploaded R object is untrusted code
# (CVE-2024-27322). See DESIGN.md.

library(mcptools)

# Attached, not merely installed. readRDS loads a class definition's namespace
# on demand, but S4 methods are only dispatched for an attached package: with
# SingleCellExperiment left to load lazily, dim() on a restored object returns
# NULL and assayNames() is not found. Paying the startup cost once in a
# long-lived server is the cheap side of that trade.
suppressPackageStartupMessages({
  library(SingleCellExperiment)
})

source("datasets.R")

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
REPORTED_PACKAGES <- c(
  "mcptools", "httpuv", "jsonlite", "SingleCellExperiment", "anndataR"
)

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

# The first tool that opens a researcher's file. Everything about this
# container -- no network, no credentials, read-only filesystem, dropped
# capabilities -- exists so that this call is survivable: readRDS on a file we
# did not create is equivalent to running code we did not write
# (CVE-2024-27322).
#
# It reports structure, never contents. What the adapters need to know is what
# kind of object this is, and that is also what Phase 7.0 is waiting on for
# the pilot dataset.
inspect_rds_impl <- function(dataset_id, filename) {
  run_tool(function() {
    path <- resolve_upload(dataset_id, filename)

    object <- tryCatch(
      readRDS(path),
      error = function(e) {
        stop(
          sprintf("'%s' could not be read as an R object: %s", filename, conditionMessage(e)),
          call. = FALSE
        )
      }
    )

    dimensions <- if (is.null(dim(object))) NULL else as.integer(dim(object))

    jsonlite::toJSON(
      list(
        dataset_id = dataset_id,
        filename = filename,
        class = class(object),
        is_s4 = isVirtualClass(class(object)[1]) || isS4(object),
        dimensions = dimensions,
        # Present only for the container types the adapters care about, and
        # asked for defensively: an arbitrary object has no assays.
        assay_names = tryCatch(
          if (methods::is(object, "SummarizedExperiment")) {
            SummarizedExperiment::assayNames(object)
          } else {
            NULL
          },
          error = function(e) NULL
        )
      ),
      auto_unbox = TRUE,
      null = "null"
    )
  })
}

inspect_rds <- ellmer::tool(
  inspect_rds_impl,
  description = paste(
    "Inspect an uploaded .rds file and report what kind of R object it holds:",
    "class, dimensions and assay names. Reports structure, not contents."
  ),
  arguments = list(
    dataset_id = ellmer::type_string("The dataset's opaque ID."),
    filename = ellmer::type_string("The file name within that dataset.")
  ),
  name = "inspect_rds"
)

cat(sprintf("%s starting MCP server on 0.0.0.0:%d\n", COMPONENT, PORT))
flush(stdout())

# session_tools = FALSE: the default exposes list_r_sessions and
# select_r_session, which let a caller route tool calls into an interactive R
# session over a local socket. That is a developer convenience and, in a
# container whose job is to open untrusted files, an extra door.
mcp_server(
  tools = list(runtime_versions, inspect_rds),
  type = "http",
  host = "0.0.0.0",
  port = PORT,
  session_tools = FALSE
)
