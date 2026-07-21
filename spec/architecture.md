# Architecture

---

## System Overview

A FastAPI backend serves a Next.js static-export chat UI at `/app/`. Users upload CSVs, which are parsed and profiled, then persisted (file + profile) so the same dataset can be queried across a session and across days. Questions are answered by a LangGraph agent that never sends raw data rows to the LLM — it sends only column schema/dtypes/aggregate stats plus the user's question, gets back generated pandas code, and executes that code itself, server-side, against the real in-memory dataframe. Results (prose + optional table/chart) return to the chat UI, and every question/code/result triple is written to an audit-log table in Postgres.

## Component Map

```
Next.js chat UI (frontend/)
    ↓  upload CSV / POST question
FastAPI routers (src/api/datasets.py, src/api/sessions.py)
    ↓                              ↓
csv_profiling.py (src/tools/)     LangGraph agent (src/graph/)
    ↓                              ↓         ↑ (schema/question/code only, no rows)
Postgres: datasets, sessions,    NVIDIA NIM LLM  ←→  code_sandbox.py (src/tools/)
turns, audit_log_entries              (src/llm/)         ↓ (executes against real dataframe)
                                                    real uploaded CSV data
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (`src/api/`) | HTTP routes: dataset upload/list/profile, session create, message post |
| Agent (`src/graph/`) | LangGraph state machine: classify → generate code → execute → reflect/retry → summarize |
| Tools (`src/tools/`) | Pure functions: CSV → profile dict; (code, dataframes) → result or exception |
| LLM (`src/llm/`) | Provider-agnostic client; NVIDIA NIM adapter for this project |
| Storage (`src/db/`) | Postgres via SQLAlchemy: datasets, sessions, turns, audit log |

## Data Flow

1. Trigger: user uploads one or more CSVs via the chat UI → `POST /api/datasets`.
2. `csv_profiling.py` parses each file with pandas, computes row/column counts, dtypes, null counts, duplicate-row count; a `Dataset` row is written (file persisted under `data/uploads/`, profile stored as JSON); the profile returns immediately to the UI.
3. User creates/continues a session bound to one or more `dataset_ids` (`POST /api/sessions`) and asks a question (`POST /api/sessions/{id}/messages`).
4. The LangGraph runner loads the session's dataset schema(s) (columns/dtypes/stats only — never rows) and recent conversation turns, then invokes the graph: `load_context` → `classify_intent` (ambiguous → short-circuit with a clarifying question) → `generate_code` (LLM writes pandas code against the real dataframe(s) by name) → `execute_code` (runs server-side, in a restricted sandbox, against the real data) → on error, `reflect_on_error` feeds the exception back to the LLM and loops to `generate_code` (bounded, max 3 attempts) → `finalize_answer` (LLM summarizes the real computed result into prose + a table/chart representation).
5. Output: prose answer + optional table rows + optional chart spec + a token/cost estimate, returned to the chat UI; the audit-log row and conversation turn are both persisted in the same request.

## Data Residency Enforcement (binding constraint)

The `classify_intent`, `generate_code`, and `reflect_on_error` prompts include ONLY column names, pandas dtypes, basic aggregate stats (count/min/max/null-count per column), the user's question, and (for reflection) the Python exception text — never actual cell values or row samples. `execute_code` runs entirely server-side; only the numeric/aggregate output that `finalize_answer` chooses to summarize is passed to the LLM for prose generation — never a raw row dump. This schema-only-prompting, local-execution pattern is the intended template for the Phase 3 MSSQL integration.

## Forward-looking: MSSQL (Phase 3 design intent, not built yet)

Phase 3 adds a read-only connection (ideally a read replica, never the primary write path) with: schema introspection reused by the same `generate_code` node, parameterized SQL generation (never raw string interpolation), query timeouts and row-count caps, a TTL-based result cache keyed on (generated SQL, params) so repeated questions don't re-hit the production DB, and sampling/pagination for multi-million-row tables. Documented here so Phase 1/2 code (the schema-context abstraction in `src/graph/nodes.py`) is written so Phase 3 can extend it rather than rewrite it — schema context is sourced from an abstract "data source" concept, not hardcoded to "CSV file."

## Code Execution Sandbox

`src/tools/code_sandbox.py` executes LLM-generated pandas code via `exec()` with: no `__import__` access (only `pandas as pd` and the loaded dataframe(s) are in scope), a wall-clock timeout (5s) via a worker thread, and no filesystem/network access from within the executed code. This is a pragmatic in-process sandbox for Phase 1 (trusted deployment, single shared workspace) — not a hardened multi-tenant sandbox. Phase 2's access-control work should revisit isolation strength once the deployment is multi-tenant.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| NVIDIA NIM API (`integrate.api.nvidia.com`) | LLM calls: intent classification, code generation, error reflection, answer summarization | Surface a clear "analysis unavailable, try again" error to the user; log the failure; never crash the request |
| PostgreSQL | Datasets, sessions, turns, audit log | App fails to start / requests fail fast with a clear DB-connection error; no silent data loss |
| Local filesystem (`data/uploads/`) | Persisted CSV files | Upload fails with a clear error if disk write fails; no silent partial dataset |

## Stack

- **Language:** Python 3.11+ (backend), TypeScript (frontend).
- **Agent framework:** LangGraph — a bounded self-correction state machine (see `spec/agent.md`).
- **LLM provider + model:** NVIDIA NIM (OpenAI-compatible REST API), model `meta/llama-3.1-70b-instruct`, via a new `src/llm/providers/nvidia.py` adapter using the `openai` Python SDK pointed at `base_url=https://integrate.api.nvidia.com/v1`. Env vars (already in `.env`): `AGENT_LLM_PROVIDER=nvidia`, `AGENT_NVIDIA_API_KEY`, `AGENT_LLM_BASE_URL`, `AGENT_LLM_MODEL`.
  > **Assumed:** the NVIDIA NIM chat-completions endpoint is OpenAI-compatible (the standard NIM integration pattern); `openai` is added as a new dependency for this adapter only.
- **Backend:** FastAPI (existing).
- **Database + ORM:** PostgreSQL + SQLAlchemy 2.0 + Alembic, upgraded from the skeleton's SQLite default. Driver: `psycopg2-binary`, declared in `[project.dependencies]` (never dev-only).
  > **Assumed:** a local PostgreSQL instance for development (installed via winget on this machine — none was present). Production would point the same `AGENT_DATABASE_URL` at a managed Postgres instance.
- **Frontend:** Next.js 15 + React 19, static export (`output: 'export'`, `basePath: '/app'`) served by FastAPI — existing pattern, extended with a chat UI in place of the transform-text form.
- **Dependency management:** `uv` (Python), `pnpm` (frontend — installed via corepack on this machine).
- **Data processing:** `pandas` (new dependency) — CSV parsing, profiling, and the execution context for generated analysis code.

| Key library | Version | Purpose |
|-------------|---------|---------|
| pandas | >=2.2 | CSV parsing, profiling, analysis execution context |
| openai | >=1.40 | NVIDIA NIM client (OpenAI-compatible endpoint) |
| psycopg2-binary | >=2.9 | PostgreSQL driver |
| langgraph | >=0.1 (existing) | agent state machine |

**Avoid:** no ORM "repository pattern" wrapper (direct SQLAlchemy queries per `harness/patterns/project-layout.md`); no arbitrary `eval`/`import` inside generated code (the sandbox explicitly blocks it); no raw-row transmission to the LLM under any code path.

- **Observability:** structured request/response/latency logging via the existing `structlog`-based `src/observability/events.py`, extended to log every graph-node LLM call and every code execution (input size, latency, success/failure) to stdout.
  > **Assumed:** LangSmith tracing is not wired — it requires `LANGCHAIN_API_KEY`, which wasn't part of intake and isn't a hard requirement; structured stdout logging plus the DB-backed audit log (a superset — full input/output/timestamp per interaction) satisfies the observability requirement instead.
- **E2E testing:** Playwright, `tests/e2e/`.
- **Git/PR:** GitHub CLI (`gh`, installed via winget on this machine) against `https://github.com/devtshq-star/dev-zero-shot-claude-harness.git`.

## Deployment Model

Long-running local service: `uv run python -m src` serves FastAPI (including the built Next.js static export) on `http://localhost:8001`. Postgres runs as a local service (or a managed instance in production, via `AGENT_DATABASE_URL`). No background workers in Phase 1 — each chat message is answered synchronously within the HTTP request (bounded by the 3-attempt retry cap and per-call LLM timeouts, so requests stay within the ~30s target).
