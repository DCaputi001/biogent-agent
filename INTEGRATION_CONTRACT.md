# INTEGRATION_CONTRACT.md

Every point where biogent-agent will meet the main BioGent project.

This exists because the two are built in separate repos, at different times.
The main repo's upload path, auth, and storage layout can all move while this
service is being built, and the cost of discovering that at import time is much
higher than the cost of writing it down now.

**How to use it:** when the main repo changes something described here, update
this file *then* — not at 7.8, and not at import. A contract that is only
checked at the end is a description of what went wrong, not a way to prevent it.

Each item below is marked:

- **VERIFIED** — read from the main repo's code on the date noted, with the
  file named. Trust it, but re-check before the import.
- **TBD** — decided when the code that needs it is written.

Last verified against the main BioGent repo: **2026-09-24**.

---

## 1. Identity: who is asking

**VERIFIED** — `services/rag/app/auth.py`.

The main project authenticates with **Amazon Cognito access tokens**, verified
locally rather than by calling AWS:

- `Authorization: Bearer <token>`, scheme matched case-insensitively.
- RS256 only, pinned. Anything else — including `alg: none` — is rejected.
- Keys come from the pool's JWKS endpoint
  (`https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json`),
  cached per process.
- `token_use` **must** be `"access"`. An *ID* token from the same pool carries
  a valid signature and issuer and would otherwise be accepted.
- `client_id` is checked **explicitly**, because Cognito access tokens carry no
  `aud` claim — audience verification is turned off, and this check stands in
  for it. Dropping it would leave a token unbound to any app client.
- Required claims: `exp`, `iss`, `sub`.
- The user id is the Cognito **`sub`**, treated as an opaque string.

**What this service does:** the same verification, against the same pool. Not a
new auth mechanism, and not a trusted header passed along by another service.

**TBD:** whether the orchestrator verifies tokens itself or sits behind
something that already has. Verifying it directly is the cheaper default —
`auth.py` is ~150 lines and one dependency.

---

## 2. Payment: who pays for the model calls

**VERIFIED** — `services/rag/app/api.py`.

The researcher brings their own Anthropic key. It arrives per request in the
**`X-Anthropic-Api-Key`** header, is used for that request, and is **never**
persisted server-side.

The two credentials answer different questions and neither substitutes for the
other: **the bearer token decides whose data is used; the API key decides who
pays.** Missing either one is a 401.

**What this service does:** identical. Additionally — and this is stricter than
the RAG service needs to be — **the key never leaves the orchestrator.** It is
not passed to any MCP server, because those are sandboxes holding untrusted
data, and a credential in one is a credential that can be exfiltrated by
whatever the sandbox just opened.

This service makes many more model calls per task than the RAG service does, so
the cost controls in `DESIGN.md` (pre-run estimate, hard token caps) are part
of this contract, not a nicety.

---

## 3. Storage: where datasets live

**VERIFIED** — `services/rag/app/storage.py`, `app/config.py`.

- Key layout: **`users/{user_id}/documents/{filename}`**, built by
  `storage.build_user_key()`. The prefix root is `config.USER_UPLOAD_PREFIX`
  (`"users"`).
- The `user_id` in that key comes **from the verified token, never from the
  request body** — which is what makes the prefix unable to point at another
  researcher's data.
- Filenames are sanitized before they become keys, truncating the stem and
  preserving the suffix, because the extension is what decides how the file is
  parsed.
- Uploads go **browser → S3 directly**, via a **presigned POST** (not PUT):
  only POST carries a policy, and the `content-length-range` condition on it is
  what makes the size limit enforced by S3 rather than merely requested of the
  client. Default cap 50 MB, URL TTL 900s.
- The key is fixed by the policy, so a caller cannot redirect an upload
  elsewhere.
- Downloads defend against keys like `../../evil` resolving outside the
  destination directory (`storage._safe_local_path`). S3 keys are arbitrary
  strings and a malicious one is legal in a bucket.

**What this service does:** the data-access MCP server resolves an opaque
**dataset ID** to a location. Locally that is a folder under `data/`. After
import it is `users/{user_id}/datasets/…` — the same discipline, one directory
level over from documents.

**The agent never sees or constructs a key.** See `DESIGN.md`, "the agent never
constructs a file path."

**TBD:** the exact prefix for datasets (`datasets/` vs reusing `documents/`),
and whether an `.rds` plus its companion marker CSVs are one dataset ID or
several.

---

## 4. Handoff: starting background work

**VERIFIED** — `services/rag/app/queue.py`, `app/worker.py`, `app/api.py`.

The pattern the main repo already uses, and the one to copy:

- The browser tells the API the upload finished
  (`POST /api/documents/{id}/complete`); the API commits the row **first**, then
  enqueues.
- The SQS message body is **only** `{"document_id": "<uuid>"}`. Everything else
  about the document lives in the `documents` table. A message carrying its own
  copy of the filename or key would be a second source of truth that goes stale
  the moment a row is corrected.
- The worker long-polls (20s, the SQS maximum), takes **one** message at a
  time, and deletes it after handling. Batching would hold messages invisible
  behind work that has not started, and they would time out and be redelivered.
- Document lifecycle: `pending → processing → ready | failed`, enforced by a
  CHECK constraint (`services/rag/app/models.py`).
- A document-specific failure never raises out of the worker loop — it marks
  the row `failed` and moves on, so one bad file does not stop the queue.

**What this service does:** the same shape for long-running analysis jobs, with
a local queue standing in for the real one. The important difference is
**duration** — RAG ingestion is minutes, an analysis run is potentially hours —
which is why the run state lives in LangGraph checkpoints rather than in a
visibility timeout.

**TBD:** whether analysis jobs share the existing SQS queue with a message type
discriminator, or get their own. Leaning toward their own: the two have very
different timeout profiles.

---

## 5. Orchestrator API surface

**TBD** — this service's own API, designed when the orchestrator is built. The
shape it has to support:

| Operation | Purpose |
|---|---|
| start a run | dataset ID(s), species/annotation, budget tier |
| check status | which stage, progress on long jobs |
| answer a prompt | a LangGraph interrupt asking the researcher to confirm something inferred rather than read |
| fetch reports | thesis reports and the reproducibility bundle |

Constraints already fixed by the sections above: routes live under `/api`
(`APIRouter(prefix=...)` in the RAG service), every route takes both
credentials, and a run belongs to the `sub` that started it.

---

## 6. Persistence

**VERIFIED** — `services/rag/app/db_credentials.py`, `AGENTS.md`.

The main project runs **PostgreSQL + pgvector on RDS**, with schema migrations
in **Alembic**, and one hard rule: the database password lives **only in AWS
Secrets Manager**. Code sets `RAG_DB_SECRET_ID` and reads the connection
through `db_credentials.get_database_url()` — never a `DATABASE_URL` constant.

Alembic's `include_object()` filters out the `langchain_pg_*` tables, which are
owned by langchain-postgres. A migration that tries to manage them is a bug.

**What this service does:** LangGraph checkpoints in local Postgres now
(`docker-compose.yml`, port 5433), RDS after import — reading credentials the
same way, and never holding a password in this repo.

**TBD:** whether checkpoints share the RAG database or get their own. Sharing
is simpler; a separate database is easier to reason about when the thing
writing to it is orchestrating sandboxes.

---

## 7. Frontend

**TBD** — built at 7.9 Part B, in the main repo.

One constraint is already fixed and worth recording, because getting it wrong
ships something broken to production: **`frontend/**` is on the main repo's
deploy path**, so any frontend work for this service merges straight into the
next production release. It ships **behind a feature flag, off by default**,
until the backend exists in production.

---

## Change log for this contract

| Date | What changed in the main repo | What changed here |
|---|---|---|
| 2026-09-24 | — | First version, verified against the main repo. |
