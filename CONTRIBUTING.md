# Contributing to biogent-agent

Adapted from the main BioGent repo's `CONTRIBUTING.md`, deliberately: this code
is imported into that repo at Phase 7.9, and two repos with different habits
make that import more expensive than it needs to be.

---

## Branching model

- **Never commit directly to `main`.** All work on a `feature/*` or `fix/*`
  branch, merged via pull request — even solo. This is what makes CI
  meaningful: checks run *on the PR*, before anything reaches `main`.
- **`main` is always in a working state.** Not "deployable" here, since nothing
  in this repo deploys, but `docker compose up` and `uv run pytest -q` should
  both work on any commit on `main`.
- Branch naming: `feature/short-description`, `fix/short-description`.

### Multi-machine workflow (PC + laptop)

- **Push before switching machines. Pull before starting work.**
- Directories with no tracked files inside them will **not** survive a fresh
  clone — git does not track empty directories. A new component directory needs
  a `.gitkeep` until it holds real content. `tests/test_repo_invariants.py`
  checks this for the known layout.
- `BIOGENT_PLAN.md` is git-ignored, so it does **not** travel between machines
  with the repo. Copy it across by hand, or keep it in whatever you already use
  for private notes.

---

## Pull requests

- Every PR should have a diff worth reviewing.
- CI runs automatically on every PR. A PR should not be merged with a failing
  check.
- **A PR that modifies files under `tests/` deserves extra scrutiny** —
  especially if it is the *only* thing that changed, with no corresponding
  implementation change. See below.

---

## Protecting tests from being silently weakened

The failure mode to guard against: an agent (or a person, under deadline
pressure) hits a failing test and, instead of fixing the underlying code,
"fixes" the test — loosens an assertion, deletes a case, or changes an expected
value to match new and possibly buggy behavior.

This matters more here than in the RAG service. A retrieval bug returns a bad
answer the researcher can see. A statistics bug returns a plausible number that
looks exactly like a real finding, and the eval suite is the only thing
standing between that and a thesis report.

**What is set up:**
- The explicit rule in `AGENTS.md`, stated as a hard rule with its reasoning.
- Tests written against observable behavior rather than internals, so a
  superficial edit to make one pass is visible in review.
- `evals/` holds the checks that cannot be unit tests — reproduction of known
  results (7.4) and planted-signal detection (7.7). Their reports are
  committed, so a regression shows up as a diff.

**Worth adding once there is more history:** a branch protection rule requiring
review before merge to `main`, and a CI check that flags a PR touching only
test files.

---

## Where design decisions live

`DESIGN.md` for this service's own decisions. `INTEGRATION_CONTRACT.md` for
anything at the boundary with the main BioGent repo — and if the main repo
changes something on that boundary, update the contract **when it happens**,
not at import time. Discovering the drift at 7.9 is what the document exists to
prevent.

---

## For AI coding agents

See `AGENTS.md`.
