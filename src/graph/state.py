from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    session_id: str
    dataset_ids: list[str]

    # Input
    question: str
    language: str                  # UI language ("en"|"hi") — preferred answer language

    # Pipeline data
    schema_context: dict           # {dataset_name: {"columns": [...], "row_count": int}}
    dataframes: dict               # {dataset_name: pd.DataFrame} — loaded once per run, never sent to the LLM
    conversation_history: list     # [{"role": "user"|"assistant", "content": str}, ...]
    needs_clarification: bool
    clarification_question: str | None
    generated_code: str | None
    exec_result: dict | None       # {"value": ..., "table": [...] | None, "error": str | None}
    attempts: int
    total_token_usage: dict        # accumulated {"prompt_tokens", "completion_tokens", "estimated_cost_usd"}

    # Output
    final_answer: str | None
    table_data: list | None
    chart_spec: dict | None
    follow_ups: list | None

    # Control
    error: str | None
    status: str                    # "pending" | "clarification_needed" | "completed" | "failed"
