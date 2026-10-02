# AGENTS.md

Orientation for AI coding agents working in the `biogent-agent` repository.

This repo is **not** the main BioGent repo. It is a standalone workspace for
building BioGent's bioinformatics analysis agent, which will be imported into
the main repo as `services/bio-agent/` once it works. Until then, nothing here
deploys anywhere.

---

## What this is

A researcher hands biogent a dataset. Biogent organizes it, explores it, and
returns a small number of well-supported theses worth pursuing — or reports
that nothing survived scrutiny. Single-cell RNA-seq first; other data types are
later modules.

The shape of it:

- a **LangGraph orchestrator** (`orchestrator/`)
- **MCP servers, one per runtime**, each in its own sandbox
  (`servers/python-analysis/`, `servers/r-analysis/`, `servers/data-access/`)
- an **eval harness** (`evals/`), the same pattern as `services/rag/evals/` in
  the main repo

Read `DESIGN.md` before proposing an architectural change, and
`INTEGRATION_CONTRACT.md` before changing anything at the boundary with the
main BioGent project. Several things that look like open questions are already
decided there, with reasoning.

---

## Repo layout

```
biogent-agent/
├── orchestrator/              # LangGraph graph
├── servers/
│   ├── python-analysis/       # sandboxed Python analysis tools (MCP)
│   ├── r-analysis/            # sandboxed R analysis tools (MCP)
│   └── data-access/           # resolves dataset IDs to storage (MCP)
├── evals/                     # cases.py, run_evals.py, reports/
├── tests/                     # unit tests, including repo invariants
├── DESIGN.md                  # design decisions and reasoning — read first
├── INTEGRATION_CONTRACT.md    # every point where this meets the main repo
├── CONTRIBUTING.md            # branching model, PR workflow
└── docker-compose.yml         # local stack
```

Every path in this repo is relative to its root, because the whole tree is
moved into `services/bio-agent/` at import. `tests/test_repo_invariants.py`
enforces that.

---

## How to run things locally

```powershell
uv sync
uv run ruff check .
uv run pytest -q

docker compose build
sh scripts/generate-fixtures.sh
docker compose up -d --wait

# Runtime isolation and ingestion tests. Needs the stack up; CI runs these too.
$env:BIOGENT_REQUIRE_DOCKER_STACK = "1"; uv run pytest -q -m docker
```

Test datasets are generated, never committed. `sh scripts/generate-fixtures.sh`
writes them into `data/uploads/`; `tests/fixtures/spec.py` is the single
description of what they contain, imported by both the generators and the
tests.

The analysis servers sit on `internal` Docker networks with no route out and
no route to Postgres. If something you are building seems to need a sandbox to
reach the network or the database, that is a design question for `DESIGN.md`,
not a line to add to `docker-compose.yml`.

Every tool body goes through `run_tool` (`common/mcp_app.py`, and the R
equivalent in `servers/r-analysis/main.R`), which enforces a wall-clock limit
by killing the process running it. A tool that bypasses it is a tool that can
hold a sandbox indefinitely.

Local only, by design. There is no staging environment and no deploy command
in this repo, and adding one is a change to its security posture, not a
convenience.

---

## Explicit "don't" list

- **Never load an uploaded file outside the sandbox.** Uploaded `.rds` files
  are deserialized R objects, and R deserialization is a known remote code
  execution path (CVE-2024-27322). Reading one in the orchestrator process, or
  in any container that has network access or credentials, defeats the entire
  security design. This is the single most important rule in this file.
- **Never let the LLM compute a statistic itself.** The model calls a curated
  library of tested, parameterized tools; it does not do arithmetic, and it
  does not write free-form analysis code on the main path. A number that came
  out of a language model is not a result.
- **Never add AWS credentials, a deploy job, ECR, or Terraform to this repo.**
  The absence is the point — see the first rule for why. Deployment belongs to
  the main BioGent repo, after the import. CI fails if any of this appears.
- **Never commit real research data.** Pilot researchers' datasets are
  unpublished and belong to them. `data/`, `uploads/`, `*.h5ad` and `*.rds` are
  git-ignored on purpose. Synthetic fixtures for tests are fine and belong in
  `tests/`.
- **Never commit `BIOGENT_PLAN.md`.** It is local-only. `.gitignore` covers it
  and CI checks that it has never appeared in history.
- **Never store the researcher's Anthropic API key.** It arrives per request,
  lives in the orchestrator for the duration of that request, and is never
  written to disk, logged, or passed to any MCP server. This mirrors the main
  repo's BYO-key decision.
- **Never modify a file under `tests/` in order to make a failing test pass.**
  The default assumption is the *implementation* is wrong, not the test. If a
  test genuinely is wrong or outdated, say so explicitly and flag it for human
  review in the PR description — do not silently loosen an assertion, delete a
  case, or change an expected value to match new (possibly buggy) behavior.
  This applies to `evals/cases.py` as much as to `tests/`: the whole point of
  both is to catch regressions that an agent, or a person, might otherwise
  accept without noticing.

---

## Status

Scaffolding. See `DESIGN.md` for the intended shape and the local build plan
for the current sub-phase.
