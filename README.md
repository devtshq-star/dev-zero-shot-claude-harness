# UP Police Data Analyst Agent

> **All commands below run from the repo root** (this directory — there is no subdirectory to `cd` into for the backend).

A chat-based data analyst agent for UP Police. Upload one or more CSV datasets (crime/FIR records, case/investigation records, personnel rosters, traffic data) and ask questions about them in plain language. The agent writes and runs real analysis code against your actual data — never a guessed or hallucinated number — and never sends raw data rows to the LLM (only column schema, your question, and generated code leave the server).

Phase 1 (this build): CSV upload + profiling + chat Q&A + conversation memory + full audit logging. Phase 2 (multi-file joins, proactive insights, export, access control) and Phase 3 (live MSSQL connection with caching/sampling) are described in [`spec/roadmap.md`](spec/roadmap.md).

---

## Prerequisites

- Python 3.11+ and [`uv`](https://astral.sh/uv)
- Node.js 20+ and `pnpm` (`corepack enable && corepack prepare pnpm@latest --activate` if you don't have it)
- A running PostgreSQL instance (see below if you don't have one)
- An NVIDIA NIM API key (or Anthropic/Gemini — see `.env.example`)

## Setup

```bash
cp .env.example .env
```

Edit `.env`:
- Set exactly one provider key — `AGENT_NVIDIA_API_KEY` (recommended, matches `AGENT_LLM_BASE_URL=https://integrate.api.nvidia.com/v1`), or `AGENT_ANTHROPIC_API_KEY`, or `AGENT_GEMINI_API_KEY`.
- Set `AGENT_DATABASE_URL` to a real PostgreSQL connection string, e.g. `postgresql://postgres@localhost:5433/up_police_agent`.

**If you don't already have PostgreSQL:** this project was built and tested against a portable (no-admin-install) PostgreSQL — download the "binaries" zip for your platform from [postgresql.org](https://www.postgresql.org/download/), extract it, then:

```bash
/path/to/pgsql/bin/initdb.exe -D /path/to/data -U postgres -A trust
/path/to/pgsql/bin/pg_ctl.exe -D /path/to/data -l pg.log -o "-p 5433" start
/path/to/pgsql/bin/createdb.exe -p 5433 -U postgres up_police_agent
```

Then install dependencies:

```bash
uv sync --extra dev
```

## Running

```bash
uv run python agent.py            # verify tools, .env, deps, tests
uv run python agent.py --run       # apply migrations, build frontend, start server
```

`agent.py --run` applies Alembic migrations, builds the Next.js frontend, and starts the server on port 8001.

Once running:

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | **UI** — upload CSVs and chat |
| `http://localhost:8001/health` | API health check |
| `http://localhost:8001/docs` | Interactive API docs (Swagger) |

## Database migrations

```bash
uv run alembic upgrade head
uv run alembic current           # must show a revision hash, not blank output
```

A second, isolated database is used for tests — create it once:

```bash
/path/to/pgsql/bin/createdb.exe -p 5433 -U postgres up_police_agent_test
```

and set `TEST_DATABASE_URL` in `.env` to point at it (see `.env` in this repo for the exact value used in development).

## Tests

```bash
uv run pytest tests/unit/ -v          # no LLM key needed (real Postgres required)
uv run pytest tests/ -v               # full suite, requires a real LLM key in .env
```

End-to-end UI test (requires the server running at `http://localhost:8001/app/` — run `uv run python agent.py --run` first, in a separate terminal):

```bash
npx playwright test tests/e2e/ --reporter=line
```

## Project layout

```
src/
  api/              FastAPI routers: health, datasets (upload/list/profile), sessions (create/list/detail/messages)
  config/           Pydantic settings (DB URL, LLM provider/key/model, upload dir, sandbox limits)
  db/                SQLAlchemy models (Dataset, ConversationSession, ConversationTurn, AuditLogEntry) + session
  domain/            Pydantic request/response models
  graph/             LangGraph Q&A agent: state, nodes, edges, compiled graph, runner
  llm/               LLM client + providers/ (nvidia, anthropic, gemini)
  tools/             csv_profiling.py, code_sandbox.py — pure functions, no LLM calls
  prompts/           classify_intent.md, generate_code.md, finalize_answer.md
frontend/            Next.js chat UI (static export, served by FastAPI at /app)
tests/
  unit/              no LLM key needed, real Postgres required
  integration/        requires a real LLM key
  e2e/                Playwright smoke test against the live app
spec/                 roadmap, architecture, agent graph, capabilities, data model, API, UI
```

## What's real vs. what's coming

Everything in Phase 1 is real: CSV upload and profiling run against your actual files; every answer is computed by executing generated code against the real data (not a canned response); conversation history and audit log entries are persisted in Postgres. There are no non-functional stub buttons in the UI — MSSQL connectivity, export, access control, and proactive insights are simply not present yet rather than shown as disabled placeholders (see `spec/roadmap.md` for what each later phase adds).

## Rules AI Agents Follow

Full rules in `harness/rules/ai-agents.md`. Summary:

- Read the full spec before writing any code
- Never skip a phase; commit every logical unit
- Tests run against the real LLM/API using keys from `.env` — stubbed runs do not count as passing
- Each phase is tested by the human before the next phase starts
