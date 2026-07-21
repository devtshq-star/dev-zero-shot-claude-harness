# Roadmap

---

## What This Agent Does

A data analyst agent for UP Police. Analysts, station officers, and senior officials upload CSV datasets (crime/FIR incident records, case/investigation records, personnel/deployment rosters, traffic/accident data) and ask questions about them in a chat interface. The agent writes and runs real analysis code against the uploaded data and answers with actual computed numbers, tables, and charts — never a canned or hallucinated figure. It solves the problem of needing a data analyst on call for every ad hoc question by letting any user query structured records directly, in plain language, while keeping raw police records off any external LLM API. A later build extends the same engine to query a live MSSQL crime-records database directly, with caching and sampling to keep latency low and load on the production DB minimal.

## Who Uses It

- **Analysts** — ad hoc exploratory analysis, several times a day.
- **Station officers** — on-demand questions about datasets relevant to their station/district.
- **Senior officials** — periodic (weekly/monthly) briefings and summaries.

All three are in scope for this build; Phase 1 does not yet distinguish between them (no access control — see Out of Scope).

## Core Problem Being Solved

Today, answering "how many thefts in Lucknow last month" or "which stations have the most pending cases" requires a person who knows SQL/Excel to manually pull and process the data — slow, and it doesn't scale to every officer who has a question. This agent lets anyone ask directly, in natural language, and get a real, computed answer from the actual uploaded data.

## Success Criteria

- [ ] A user can upload one or more CSVs and immediately see an auto-generated profile (row/column counts, types, obvious data-quality issues) with zero manual steps.
- [ ] A user can ask a natural-language question about the uploaded data and get back a prose answer containing the real computed numbers (not a guess), backed by code that actually ran against the real dataframe.
- [ ] When a question is genuinely ambiguous (e.g. an unclear column reference), the agent asks a clarifying question instead of guessing silently.
- [ ] Conversation history persists within a session and across days for the same uploaded dataset(s) — follow-up questions like "and last month?" work without re-explaining context.
- [ ] Every question asked, the code generated to answer it, and the result produced are logged to the database with a timestamp — a full audit trail exists for every interaction.
- [ ] Raw dataset rows are never transmitted to the LLM provider — only schema/column metadata, the user's question, and generated code round-trip externally; all row-level computation happens server-side.

## What This Agent Does NOT Do (Out of Scope)

- **Phase 1 does not connect to MSSQL.** CSV upload is the only data source until Phase 3.
- **Phase 1 has no access control.** Single shared workspace — every user sees every uploaded dataset. District/role/dataset-ownership-based access control is explicitly deferred to Phase 2, and MUST be in place before any production MSSQL rollout (see Key Constraints).
- **No PDF/CSV export of results** until Phase 2.
- **No proactive anomaly flagging or follow-up-question suggestions** until Phase 2 (Phase 1 only answers what's asked).
- **No reasoning-chain or generated-code visibility in the UI** — the agent never shows its internal code/reasoning to the end user, by explicit choice, in any phase.
- **Never executes destructive operations** — no CSV row deletion/mutation, no MSSQL writes, ever. All generated code/SQL is read-only analysis.

## Key Constraints

- **Data residency (binding):** raw police-record rows must never be sent to the LLM. The LLM sees only column names/dtypes/aggregate statistics, the user's question, and generated analysis code. All row-level computation runs locally in the backend process.
- **Cost:** keep LLM spend low — use a single mid-sized model (NVIDIA NIM `meta/llama-3.1-70b-instruct`) rather than the largest available, and show per-query token/cost estimates in the UI so usage stays visible.
- **Scale (Phase 1):** uploaded CSVs up to ~100MB, answer within ~30s.
- **Scale (forward-looking, Phase 3):** the MSSQL source will have multi-million-row tables and concurrent users — Phase 3 must design for sampling/pagination, connection pooling against a read-replica where possible, and query-result caching to bound latency and DB load. Not built in Phase 1/2.
- **Audit trail (binding from Phase 1):** every question, the generated code, and the result must be persisted in the database with a timestamp — this is core, not a stretch goal, given the sensitivity of police data.
- **Reliability bar:** Phase 1 must be correct and real on its one path (not a disposable prototype) — no fake/stubbed data on the tested path.

## Phases of Development

### Phase 1 — Upload & Ask

- **Goal:** the complete primary journey end-to-end: upload one or more CSVs → see an auto-profile → ask questions in a persistent chat → get real, computed answers (prose + table/chart) → every interaction is audit-logged.
- **Independent slices (parallel build units):**
  - `slice-db` (backend) — Postgres models + Alembic migration for `datasets`, `conversation_sessions`, `conversation_turns`, `audit_log_entries`. Deps: none.
  - `slice-llm` (backend) — NVIDIA NIM provider adapter (`llm/providers/nvidia.py`) + settings + `LLMClient` wiring. Deps: none.
  - `slice-upload` (backend) — CSV upload + profiling service + `api/datasets.py` routes + domain models. Deps: `slice-db`.
  - `slice-graph` (backend) — LangGraph state/nodes/edges/runner for the Q&A agent (schema-only prompting, sandboxed code execution, bounded retry, clarification branch) + `api/sessions.py` routes. Deps: `slice-db`, `slice-llm`, `slice-upload` (needs the dataset row/dataframe access path).
  - `slice-frontend` (frontend) — chat UI (upload + message list + input), table/chart rendering, per-query cost readout, Playwright e2e smoke. Deps: none at build time (builds against `spec/api.md`/`spec/ui.md`; wired to the real backend for the gate).
- **Key surfaces / files:**
  - `slice-db`: `src/db/models.py`, `alembic/versions/000X_*.py`
  - `slice-llm`: `src/llm/providers/nvidia.py`, `src/llm/providers/__init__.py`, `src/llm/client.py`, `src/config/settings.py`
  - `slice-upload`: `src/api/datasets.py`, `src/domain/dataset.py`, `src/tools/csv_profiling.py`
  - `slice-graph`: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/tools/code_sandbox.py`, `src/api/sessions.py`, `src/prompts/*.md`
  - `slice-frontend`: `frontend/src/app/page.tsx`, `frontend/src/app/**`, `tests/e2e/`
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/ -v` (against the real Postgres DB in `.env` and the real NVIDIA API key), plus `npx playwright test tests/e2e/ --reporter=line` against the live server at `http://localhost:8001/app/`.
- **How the user tests it (handoff seed):** open `http://localhost:8001/app/`, upload a CSV (a sample crime-records CSV is provided), see the auto-profile appear, ask a real question (e.g. "how many rows are there" or "what's the breakdown by district column"), see a real computed answer with a table, ask a deliberately ambiguous question and see the agent ask a clarifying question instead of guessing. MSSQL, exports, and access control are not shown as UI stubs (chat-only interface) — their absence is expected, not a bug.

### Phase 2 — Proactive Intelligence, Multi-file Analysis & Access Control

- **Goal:** wire the deferred Phase-1 gaps into real functionality: combine multiple files into one analysis, get unsolicited data-quality/anomaly flags and follow-up suggestions, export results, and enforce access control before any production rollout.
- **Independent slices (parallel build units):**
  - `slice-multifile` (backend) — multi-dataset join/compare support in `generate_code`/`execute_code` prompting and the sandbox context (multiple dataframes addressable by name). Deps: none (extends Phase 1's `slice-graph` surfaces).
  - `slice-proactive` (backend) — anomaly/data-quality flagging during profiling and after each answer; 2–3 follow-up-question suggestions appended to each assistant turn. Deps: none.
  - `slice-export` (backend + frontend) — CSV/PDF export of a turn's result table; export button in the UI. Deps: none.
  - `slice-access` (backend) — role (analyst/officer/senior-official) and district/station scoping on datasets and sessions; dataset-ownership default-private-to-uploader; simple login/session identity. Deps: none.
- **Key surfaces / files:** `src/graph/nodes.py`, `src/tools/`, `src/api/datasets.py`, `src/api/sessions.py`, new `src/api/auth.py` + `src/domain/user.py`, `frontend/src/app/**`.
- **Gate command:** `uv run pytest tests/ -v` against real Postgres + real NVIDIA key; Playwright e2e covering multi-file join, an export click, and an access-denied case.
- **How the user tests it:** upload two related CSVs and ask a question that requires joining them; ask a normal question and see 2–3 follow-up suggestions plus any data-quality flags; click export and get a file; log in as two different roles/districts and confirm each only sees their own data.

### Phase 3 — Live MSSQL Connection with Low-Load Query Layer

- **Goal:** extend the same chat Q&A engine to answer questions against a live production MSSQL database, transparently alongside CSV datasets, without raw rows ever reaching the LLM and without adding meaningful load/latency to the source DB.
- **Independent slices (parallel build units):**
  - `slice-mssql-schema` (backend) — read-only MSSQL connection (ideally against a read replica) + schema introspection surfaced to `generate_code` the same way CSV schemas are (columns/dtypes only, never rows). Deps: none.
  - `slice-mssql-exec` (backend) — parameterized, read-only SQL generation and execution against MSSQL with query timeouts and row-count caps. Deps: `slice-mssql-schema`.
  - `slice-cache` (backend) — a query-result cache (keyed on generated SQL + params, TTL-based) sitting in front of MSSQL so repeat/similar questions don't re-hit the production DB. Deps: `slice-mssql-exec`.
  - `slice-sampling` (backend) — sampling/pagination strategy for multi-million-row tables so answers stay within the latency budget. Deps: `slice-mssql-exec`.
  - `slice-unified-chat` (backend + frontend) — a data-source picker/auto-detect so the existing chat UI can target CSV datasets or the MSSQL connection without the user needing to know which. Deps: `slice-mssql-exec`.
- **Key surfaces / files:** `src/db/mssql.py` (new connection module, separate from the app's own Postgres session), `src/graph/nodes.py`, `src/tools/query_cache.py`, `frontend/src/app/**`.
- **Gate command:** `uv run pytest tests/ -v` against a real (test) MSSQL instance + real NVIDIA key; a load/latency assertion test that a repeated question hits the cache, not MSSQL, on the second call.
- **How the user tests it:** ask a question that only the MSSQL source can answer (a table not in any uploaded CSV) and get a real computed answer; ask the same question again and confirm (via a visible cache indicator or timing) it didn't re-query MSSQL.
