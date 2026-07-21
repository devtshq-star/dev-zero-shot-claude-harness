# Agent

---

## Agent Architecture Pattern

**Chosen: Graph (LangGraph).** The primary journey is a multi-step pipeline with conditional branching (ambiguous-question short-circuit, error-driven retry loop) — not a single deterministic tool loop, and not multiple specialised agents needing an orchestrator. A graph is the natural fit and matches the existing skeleton's dependency on LangGraph.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `classify_intent`, `generate_code`, `reflect_on_error`, `finalize_answer` | NVIDIA NIM | `nvidia/llama-3.3-nemotron-super-49b-v1` | Single mid-sized model for all nodes per the cost-conscious constraint (no per-node model tiering in Phase 1) |

**Fallback behaviour:** on an API error/timeout from NVIDIA NIM, the node retries once with exponential backoff (1s); on a second failure, the graph routes to `handle_error`, which surfaces "analysis temporarily unavailable, please try again" to the user and logs the failure — the request never crashes.

**Prompt strategy:** system/user split per node, each with a focused system prompt (see `src/prompts/*.md`). `generate_code` and `reflect_on_error` require a structured output: a single fenced Python code block, extracted by regex — no other prose in that response. `classify_intent` returns a small structured decision (`{"ambiguous": bool, "clarification_question": str | null}`) via a JSON-mode/tool-call style prompt. `finalize_answer` returns free-form prose plus a structured `{"table": [...] | null, "chart": {...} | null}` block.

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `load_dataset_schema` | Loads column names/dtypes/aggregate stats for the session's dataset(s) from Postgres | `dataset_ids: list[str]` | `dict[str, SchemaContext]` | none (read-only) |
| `load_conversation_history` | Loads recent turns for the session | `session_id: str, limit: int` | `list[Turn]` | none (read-only) |
| `code_sandbox.execute` | Runs LLM-generated pandas code against the real dataframe(s) | `code: str, dataframes: dict[str, DataFrame]` | `ExecResult` (value/table/error) | none external; in-process only, no filesystem/network from inside the executed code |
| `persist_turn_and_audit` | Writes the conversation turn and the audit-log row | `session_id, question, generated_code, result_summary, latency_ms` | `turn_id: str` | DB write (`conversation_turns`, `audit_log_entries`) |

**Tool selection strategy:** rule-based — each node calls exactly the tool(s) named above in a fixed sequence; the LLM is never asked to choose which tool to call (this is a fixed pipeline, not an open tool-use loop).

**Tool failure handling:** `code_sandbox.execute` failures (exceptions raised by the generated code, or the 5s timeout) are caught and returned as an `ExecResult` with `error` set — never raised past the node — so `reflect_on_error` can act on them. `persist_turn_and_audit` failures are fatal (DB write is not optional for police-data audit requirements) and route to `handle_error`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str
    dataset_ids: list[str]

    # Input
    question: str

    # Pipeline data
    schema_context: dict          # {dataset_name: {columns: [...], dtypes: {...}, stats: {...}}}
    conversation_history: list[dict]   # [{"role": "user"|"assistant", "content": str}, ...]
    needs_clarification: bool
    clarification_question: str | None
    generated_code: str | None
    exec_result: dict | None      # {"value": ..., "table": [...] | None, "error": str | None}
    attempts: int                 # bounded retry counter, starts at 0

    # Output
    final_answer: str | None
    table_data: list[dict] | None
    chart_spec: dict | None
    token_usage: dict | None      # {"prompt": int, "completion": int, "estimated_cost_usd": float}

    # Control
    error: str | None
    status: str                   # "pending" | "clarification_needed" | "completed" | "failed"
```

---

## Nodes / Steps

### `load_context`

**Reads from state:** `session_id`, `dataset_ids`

**Writes to state:** `schema_context`, `conversation_history`

**LLM call:** no

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Postgres | `load_dataset_schema`, `load_conversation_history` | fatal — set `state.error`, route to `handle_error` |

**Behaviour:** Pulls schema/stats for every dataset in the session (never raw rows) and the last N conversation turns, populating the context the rest of the graph reasons over.

### `classify_intent`

**Reads from state:** `question`, `schema_context`, `conversation_history`

**Writes to state:** `needs_clarification`, `clarification_question`

**LLM call:** yes — small structured-decision prompt (`src/prompts/classify_intent.md`), NVIDIA NIM.

**External calls:** none beyond the LLM call (retried once on transient failure).

**Behaviour:** Given the question, schema, and recent history, decides whether the question is answerable unambiguously against the available columns. Ambiguity means e.g. an unclear column reference or a ranking without a specified metric — not "the answer is hard to compute." If ambiguous, produces one clarifying question.

### `generate_code`

**Reads from state:** `question`, `schema_context`, `conversation_history`, `exec_result` (on retry, contains the prior error)

**Writes to state:** `generated_code`, `attempts` (+1)

**LLM call:** yes — code-generation prompt (`src/prompts/generate_code.md`), NVIDIA NIM. On a retry pass (`attempts > 0`), the prompt also includes the prior generated code and its error, i.e. this node doubles as the "reflect" step rather than a separate LLM call — see Graph Assembly.

**External calls:** none.

**Behaviour:** Produces pandas code that computes the answer using the pre-loaded dataframe(s) (referenced by dataset name), given only schema/stats — never shown or given actual row values.

### `execute_code`

**Reads from state:** `generated_code`, `dataset_ids`

**Writes to state:** `exec_result`

**LLM call:** no

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| `code_sandbox.execute` | runs `generated_code` against the real in-memory dataframe(s) | non-fatal — captured into `exec_result.error`, routed back to `generate_code` if attempts remain |

**Behaviour:** Executes the generated code in the restricted sandbox against the real, locally-loaded CSV dataframe(s). Captures either a computed value/table or an exception message — never lets an exception propagate uncaught.

### `finalize_answer`

**Reads from state:** `exec_result`, `question`

**Writes to state:** `final_answer`, `table_data`, `chart_spec`, `token_usage`, `status`

**LLM call:** yes — summarization prompt (`src/prompts/finalize_answer.md`), NVIDIA NIM. Given the (already-computed, real) numeric/aggregate result, produces prose plus an optional table/chart representation.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Postgres | `persist_turn_and_audit` | fatal — set `state.error`, route to `handle_error` (the audit write is required, not best-effort) |

**Behaviour:** Turns the real computed result into a user-facing answer and persists the full audit trail (question, generated code, result, latency, timestamp) in the same request.

### `handle_error`

**Reads from state:** `error`, `run_id`

**Writes to state:** `status = "failed"`, `final_answer` (a clear, non-technical error message)

**LLM call:** no

**External calls:** logs the error with `run_id`/`session_id` context to stdout (structured logging).

**Behaviour:** Terminal path for unrecoverable failures (DB unreachable, LLM API exhausted its retry, max code-fix attempts exhausted with no successful execution). Never lets the API return a raw stack trace to the user.

---

## Graph / Flow Topology

```
START
  │
  ▼
load_context ──(error)──► handle_error ──► END
  │
  ▼
classify_intent ──(needs_clarification)──► END (returns clarification_question as the turn's answer, still logged)
  │ (not ambiguous)
  ▼
generate_code ◄────────────────────────────┐
  │                                        │ (exec_error AND attempts < 3)
  ▼                                        │
execute_code ──(exec_error, attempts<3)────┘
  │
  ├──(exec_error, attempts>=3)──► handle_error ──► END
  │
  ▼ (success)
finalize_answer ──(persist error)──► handle_error ──► END
  │
  ▼
END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `load_context` | `state["error"]` is not None | `handle_error` |
| `classify_intent` | `state["needs_clarification"]` is True | `END` (clarification returned as the answer) |
| `classify_intent` | `state["needs_clarification"]` is False | `generate_code` |
| `execute_code` | `exec_result["error"]` is not None AND `attempts < 3` | `generate_code` (self-correction loop) |
| `execute_code` | `exec_result["error"]` is not None AND `attempts >= 3` | `handle_error` |
| `execute_code` | `exec_result["error"]` is None | `finalize_answer` |
| `finalize_answer` | audit/turn persistence failed | `handle_error` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | schema context, generated code, exec result, attempt count |
| **Across runs** | Postgres (`conversation_turns`) | every user question + assistant answer, in order, per session — reloaded into `conversation_history` at the start of each run |
| **Conversation** | message history (not summarized in Phase 1) | last N turns (N=20) loaded verbatim into the `classify_intent`/`generate_code` prompts for follow-up-question context |

**Context window management:** Phase 1 loads the last 20 turns verbatim (small enough for the model's context window given short Q&A exchanges); summarization/sliding-window compaction is deferred until a session's history genuinely exceeds that bound.

---

## Error Handling & Recovery

**Node-level:** every node catches its own exceptions (LLM API errors, DB errors, sandbox exceptions); only `execute_code` errors are treated as recoverable (routed back into the self-correction loop) — all other node-level exceptions set `state["error"]` and route to `handle_error`.

**Graph-level (`handle_error` node):**
- Reads: `state.error`, `state.run_id`
- Sets `status = "failed"` and a clear, user-facing `final_answer`
- Logs the error with `run_id`/`session_id` context (structured log, no stack trace or raw exception text sent to the user)
- Terminates the graph

**Resume / retry strategy:** no cross-request resume in Phase 1 — a failed run simply returns the error to the user, who can re-ask. The in-run retry (up to 3 attempts) is the only automatic retry.

**Partial failure:** a code-execution failure is not partial — it drives the self-correction loop; a persistence failure is treated as fatal (the audit trail is a hard requirement, not best-effort) rather than degrading silently.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One structured log line per node per run (node name, run_id, session_id, latency, success/error) | stdout via `structlog` (`src/observability/events.py`) |
| **LLM calls** | Model, prompt/completion token counts, latency, node name | stdout structured log + `token_usage` returned to the UI |
| **Tool calls** | `code_sandbox.execute` inputs (code, dataset names — never row data), success/error, latency | stdout structured log |
| **Run outcome** | Status, total duration, error if any | Postgres (`audit_log_entries`) + stdout structured log |

---

## Concurrency Model

- **Run isolation:** one graph invocation per HTTP request (`POST /api/sessions/{id}/messages`); FastAPI handles concurrent requests across different sessions independently — no global run queue needed in Phase 1.
- **Parallel nodes within a run:** none — the pipeline is linear/sequential (classify → generate → execute → [retry] → finalize) by design, since each step depends on the previous step's output.
- **Checkpointing:** none (`MemorySaver`/no saver) — a run either completes or fails within a single request; no long-running/resumable execution in Phase 1.

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    load_context, classify_intent, generate_code,
    execute_code, finalize_answer, handle_error,
)
from graph.edges import (
    after_load_context, after_classify_intent,
    after_execute_code, after_finalize_answer,
)

def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("load_context", load_context)
    g.add_node("classify_intent", classify_intent)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("finalize_answer", finalize_answer)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("load_context")
    g.add_conditional_edges("load_context", after_load_context,
        {"classify_intent": "classify_intent", "handle_error": "handle_error"})
    g.add_conditional_edges("classify_intent", after_classify_intent,
        {"generate_code": "generate_code", "end": END})
    g.add_edge("generate_code", "execute_code")
    g.add_conditional_edges("execute_code", after_execute_code,
        {"generate_code": "generate_code", "finalize_answer": "finalize_answer", "handle_error": "handle_error"})
    g.add_conditional_edges("finalize_answer", after_finalize_answer,
        {"end": END, "handle_error": "handle_error"})
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```
