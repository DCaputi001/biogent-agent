# biogent-agent

The bioinformatics analysis agent for [BioGent](https://biogent.io) — built
here as a standalone service, imported into the main BioGent repo as
`services/bio-agent/` once it works.

A researcher hands it a dataset. It organizes the data, explores it, tries hard
to disprove what it finds, and returns a small number of well-supported theses
worth pursuing — or reports that nothing survived scrutiny. "No finding
survived" is a valid result.

**First data type:** single-cell RNA-seq, from `.h5ad` (AnnData) and `.rds`
(Seurat v4/v5, SingleCellExperiment, URD).

---

## Design in one paragraph

Code does the analysis; the model orchestrates. A LangGraph graph calls a
curated library of tested, parameterized analysis tools exposed over MCP, with
a separate sandboxed server per runtime — Python, R, and data access. The model
never writes free-form analysis code on the main path and never computes a
statistic itself. Uploaded files are only ever opened inside a sandbox with no
network, no credentials and no database access, because deserializing an `.rds`
file is a known remote code execution path (CVE-2024-27322).

See `DESIGN.md` for the reasoning, and `INTEGRATION_CONTRACT.md` for how this
meets the main BioGent project.

---

## Layout

```
orchestrator/              LangGraph graph
servers/python-analysis/   sandboxed Python analysis tools (MCP)
servers/r-analysis/        sandboxed R analysis tools (MCP)
servers/data-access/       resolves dataset IDs to storage (MCP)
common/                    shared code with no sandbox-forbidden dependencies
evals/                     rediscovery and planted-signal evals, with reports
tests/                     unit tests, including repo invariants
```

Every path is relative to the repo root, so the whole tree can be moved into
`services/bio-agent/` unchanged.

---

## Running it

```powershell
uv sync
uv run ruff check .
uv run pytest -q

docker compose build
docker compose up -d --wait
```

`--wait` returns only once every container reports healthy. Each component
currently serves a health endpoint and nothing else; the MCP servers replace
those handlers on the same ports.

The three servers are on Docker networks marked `internal`: no route to the
internet, and none to Postgres. Only the orchestrator crosses that boundary,
and only it publishes a port (`8000`). `tests/test_compose_isolation.py`
fails if that ever stops being true.

Local only. **This repo has no deploy path, no cloud credentials and no
infrastructure code, and that is a deliberate security property rather than an
unfinished one** — it is where untrusted uploaded files get opened. CI fails if
any of that appears. Deployment belongs to the main BioGent repo, after the
import.

---

## Status

Scaffolding: repo layout, CI, the design and integration documents, and a
container per component with the sandbox boundary in place. No MCP servers and
no analysis code yet.
