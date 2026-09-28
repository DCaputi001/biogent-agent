# DESIGN.md

Design decisions for biogent-agent and the reasoning behind them, in the same
spirit as `ARCHITECTURE.md` in the main BioGent repo. This document is folded
into that file at import (Phase 7.9).

Written to be publishable from the start: it stays at the level of design and
reasoning, and names no researcher, dataset or organism. The specifics belong
in the local build plan, which is never committed.

Sections marked **TBD** are open. Everything else is decided, and changing one
means changing this document in the same PR.

---

## Scope

Single-cell RNA-seq first. Other data types — bulk RNA-seq, variants,
sequences, phylogenomics — are later modules built against the same
orchestrator, not a rewrite of it.

Input formats at launch: `.h5ad` (AnnData), and `.rds` holding Seurat v4/v5,
SingleCellExperiment, or URD objects.

---

## Decision: code does the analysis, the model orchestrates

The model chooses *which* tool to run and *what to make of the result*. It does
not compute the result.

Concretely, it calls a curated library of tested, parameterized tools. It does
not write free-form analysis code on the main path, and it never produces a
number itself.

**Why:** a wrong number from a language model is indistinguishable from a right
one. It arrives with the same confidence, the same formatting, and no
traceback. Every statistic in a thesis report has to come from code that a
person can read, that has unit tests, and that logs its parameters — otherwise
the output is a plausible-looking claim with nothing underneath it, which is
worse than no output at all.

Every tool therefore: uses a fixed random seed, logs its parameters and the
package versions it ran under, and has unit tests on synthetic data.

---

## Decision: sandboxed MCP servers, one per runtime

Three servers, each in its own container, each exposing tools over MCP:

| Server | Holds |
|---|---|
| `servers/python-analysis` | scanpy-side analysis tools |
| `servers/r-analysis` | Seurat/SCE/URD adapters and R-side tools |
| `servers/data-access` | resolves dataset IDs to storage locations |

A job server for heavy asynchronous compute joins them later.

**Why separate runtimes rather than one container:** the R and Python
scientific stacks have genuinely incompatible dependency graphs, and pinning
both in one image means one of them is always slightly wrong. Separating them
also means the R sandbox — the one that opens untrusted files — can be locked
down harder than the rest.

### Sandbox isolation requirements

Each analysis sandbox has:

- **no network access** — no outbound route at all
- **no credentials** — no AWS keys, no database URL, no API keys in the
  environment
- **no database access**
- a **read-only filesystem** apart from one scratch directory
- **CPU and memory limits**, and a wall-clock timeout

These are verified by isolation tests in CI, not asserted in prose: outbound
calls must fail, the environment must contain no secrets, writes outside the
scratch directory must fail, and a runaway job must be killed at the timeout.

**Why this comes before anything sensitive crosses the boundary:** uploaded
`.rds` files are deserialized R objects, and R deserialization is a known
remote code execution path (CVE-2024-27322). Opening a researcher's upload is
equivalent to running code they did not write and cannot vouch for. The
sandbox is not defense in depth here; it is the only defense.

The researcher's Anthropic API key stays in the orchestrator and is never
passed to any server.

### Transport: MCP over HTTP on an internal network

The servers speak MCP over HTTP and sit on a Docker network marked
`internal`. The orchestrator is on that network as well as an ordinary one;
nothing else is.

**Why this and not stdio:** "no outbound route at all" and "the orchestrator
can call the server" sound contradictory, and the obvious way out — running
each server as a stdio subprocess of the orchestrator — quietly throws away
the container boundary that the previous section is built on. An internal
network resolves it instead: Docker attaches no gateway, so a sandbox can
reach neither the internet nor the host nor the database, while the
orchestrator can still reach the sandbox. Each runtime keeps its own image,
its own limits, and its own lifecycle.

The same reasoning puts Postgres on a second internal network shared only with
the orchestrator: a sandbox has no route to it, rather than lacking a password
for it. The layout is in `docker-compose.yml`, and
`tests/test_compose_isolation.py` fails if a sandbox is ever attached to a
network with a way out.

### The timeout kills a process, it does not ask a tool to stop

Every tool body runs in a child process that the server kills at a wall-clock
deadline (`common/tooling.py`).

**Why not a thread or a signal:** the case this exists for is a tool that has
stopped cooperating — a diverging optimisation, a runaway loop inside a
compiled routine. A thread cannot be interrupted, and a signal handler does
not run until the interpreter regains control, which is exactly what such a
loop never gives up. A process can always be killed by the operating system.
The cost is a fresh interpreter per call, which is noise next to the runtime
of real analysis.

R has no equivalent, so the R server uses `setTimeLimit`, which interrupts
where R checks for interrupts. That covers R-level loops and not compiled
ones; the container's CPU and memory limits are the backstop. The limit is
also cleared as each tool returns — left set, it applies to the server's own
event loop and takes the server down with it.

Each analysis server therefore carries one diagnostic tool that deliberately
misbehaves, so the kill path is tested through a real MCP call rather than
only in a unit test of the harness.

---

## Decision: the agent never constructs a file path

The data-access server resolves opaque **dataset IDs** to storage locations.
The agent asks for a dataset by ID and receives a handle.

**Why:** this is what keeps per-user isolation intact after the import. It
mirrors how the RAG service scopes every retrieval by `user_id` rather than
trusting a caller-supplied filter — an agent that can build its own path is an
agent that can build a path into another researcher's data, and prompt
injection from an uploaded file's contents is a live concern in exactly this
system.

Locally the resolver points at a folder. After import it points at user-scoped
S3 prefixes. The agent cannot tell the difference, which is the point. See
`INTEGRATION_CONTRACT.md`.

---

## Decision: the discovery funnel

Exploration is cheap and finding something is easy; the hard part is not
believing it. The pipeline is built around elimination:

```
protocol → hold-out split → sanity check → broad exploration
         → skeptic → confirmation on held-out data → thesis reports
```

- **Protocol first.** Before any testing, each run writes a pre-registered
  analysis protocol — the data split, the candidates to explore, the planned
  tests, the FDR method, and the stopping rules — saved unchangeable for that
  run. This is what makes the later statistics mean anything.
- **Hold-out.** Whole samples where there are enough of them; count splitting
  otherwise.
- **Skeptic.** A dedicated stage applying the failure modes specific to this
  data: double dipping (clustering and testing on the same cells),
  pseudoreplication (cells treated as replicates instead of pseudobulk), doublet
  and batch and stress artifacts, instability across seeds and resolutions,
  evidence that exists only in a UMAP, and trivial effect sizes.
- **Confirmation** on the held-out data, with Benjamini-Hochberg correction
  across everything that reached that stage. Every test is logged, including
  the ones that came back negative.

Most candidates are expected to be eliminated. That is the design working.
**"No finding survived" is a valid result** and is reported as one.

UMAPs appear in reports labeled as illustrations, never as evidence.

---

## Decision: reproduce before discovering

The first real milestone is not a new finding — it is recovering a *known* one
from a public dataset with published results, and matching researcher-provided
marker genes on real data. A low match stops the run.

**Why:** an agent that cannot rediscover what is already known has no business
proposing what is not, and without this check there is no way to tell the two
apart from the output.

---

## Decision: cost controls are part of the design, not an afterthought

The researcher brings their own Anthropic key and pays for every call, and this
service makes many more calls per task than the RAG service does.

- budget tiers (quick / standard / deep) with a cost estimate shown *before*
  the run
- hard token caps enforced by the orchestrator, not by prompting
- a smaller model for high-volume steps; the strongest model for the skeptic
  and for writing reports

---

## Open questions

- **TBD — how exploration work is divided.** Whether the broad-exploration
  stage runs as sub-agents, and along what axis they split, is decided when
  that stage is built rather than guessed now.
- **TBD — trajectory method.** One method to start with; which one depends on
  what the first real datasets look like.
- **TBD — annotation caching granularity** for non-model organisms, beyond
  "per species plus genome version."

---

## Note for Phase 7.10 (staging on AWS)

Recorded here rather than in the main repo, so that repo stays untouched until
the import.

**The main BioGent repo's Terraform has no concept of environments.** One state
key (`phase5/terraform.tfstate`), and every resource named `${var.project}-…`
with `project = "biogent"`. There is no `staging` anything to attach to, so
"deploy this to staging" is not a small change — it needs either a separate
state and naming scheme, or a separate AWS account, decided first.

Lean toward the separate account if the sandbox boundary still looks the way it
does above. A blast radius that includes production's VPC is not one this
service should have while it is opening untrusted files.
