# UI

---

## UI Type

Chat interface (single-page web app), Next.js static export served at `/app/`.

## Views / Screens

### Screen: Dataset Upload & Library

**Purpose:** Upload new CSVs and pick which existing dataset(s) to start/continue a session with.

**Key elements:**
- Drag-and-drop / file-picker upload area (accepts multiple `.csv` files at once)
- After upload, an auto-profile card per file: row/column count, column list with dtypes, any flagged data-quality issues (nulls, duplicates) — appears within seconds, no manual "process" button
- A list of previously uploaded datasets (name, row count, uploaded date) with a "resume" affordance into their existing session(s), or a "start new session" action to combine one or more into a fresh session

**Actions available:**
- Upload file(s)
- Select dataset(s) and start a session
- Resume an existing session

### Screen: Chat

**Purpose:** The primary journey — ask questions about the selected dataset(s) and see real, computed answers.

**Key elements:**
- Message thread: user questions and assistant answers, in order, restored on reopen (conversation memory)
- Assistant messages render as: prose answer, plus (when present) a data table and/or a chart, rendered inline — never as a separate download-only artifact in Phase 1
- A small per-message usage readout: tokens used and estimated cost for that query
- A "thinking" / in-progress indicator while a question is being answered (the agent may take a few seconds to write/execute/retry code)
- Text input for the next question

**Actions available:**
- Ask a question
- Answer a clarifying question the agent asks back
- Switch back to the Upload & Library screen to start a different session

## Error States

- **Upload failure** (bad file, parse error): an inline error on the specific file, naming the problem (e.g. "row 45: too many columns") — other files in the same batch still succeed independently.
- **Question failure** (LLM/analysis pipeline exhausted its retries): the assistant message shows a clear, non-technical message ("couldn't complete that analysis, please try rephrasing or ask something simpler") — never a raw stack trace or the generated code.
- **Loading**: a lightweight typing/thinking indicator while a question is in flight; the upload area shows a per-file progress/parsing state between "uploading" and the profile card appearing.
- **Empty states**: the Chat screen with no dataset selected prompts the user back to Upload & Library rather than showing a broken input; a session with no datasets available is not reachable (session creation requires at least one).

## What Is NOT Shown (labelled absence, not a bug)

The following are out of scope for Phase 1 and simply do not appear anywhere in the UI (no non-functional stub button, since a chat-only interface has no natural place for them without misleading the user): MSSQL connection settings, PDF/CSV export, login/access-control, proactive anomaly/follow-up suggestions. Their absence is expected — see `spec/roadmap.md` for when each arrives.

## Tech Stack

Next.js 15 + React 19, Tailwind CSS v4, static export (`output: 'export'`, `basePath: '/app'`) served by FastAPI at `http://localhost:8001/app/`. Charting via a lightweight client-side library (Recharts) rendering the `chart_spec` returned by the API; tables render `table_data` directly as an HTML table.
