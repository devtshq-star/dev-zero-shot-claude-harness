import json
import re
import time
from pathlib import Path

import pandas as pd

from config.settings import get_settings
from db.models import AuditLogEntryRow, ConversationTurnRow, DatasetRow
from db.session import create_db_session
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger
from tools.code_sandbox import execute_code as sandbox_execute_code

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_MAX_HISTORY_TURNS = 20

log = get_logger("graph")


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {text!r}")
    return json.loads(match.group(0))


def _extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _accumulate_usage(state: AgentState, usage: dict) -> dict:
    total = dict(state.get("total_token_usage") or {"prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0})
    total["prompt_tokens"] += usage.get("prompt_tokens", 0)
    total["completion_tokens"] += usage.get("completion_tokens", 0)
    total["estimated_cost_usd"] = round(total["estimated_cost_usd"] + usage.get("estimated_cost_usd", 0.0), 6)
    return total


def load_context(state: AgentState) -> AgentState:
    try:
        dataset_ids = state["dataset_ids"]
        schema_context: dict = {}
        dataframes: dict = {}

        with create_db_session() as session:
            for dataset_id in dataset_ids:
                dataset = session.get(DatasetRow, dataset_id)
                if dataset is None:
                    return {**state, "error": f"Dataset {dataset_id} not found"}
                schema_context[dataset.name] = {
                    "columns": dataset.profile.get("columns", []),
                    "row_count": dataset.row_count,
                    "duplicate_row_count": dataset.profile.get("duplicate_row_count", 0),
                }
                dataframes[dataset.name] = pd.read_csv(dataset.storage_path)

            turns = (
                session.query(ConversationTurnRow)
                .filter(ConversationTurnRow.session_id == state["session_id"])
                .order_by(ConversationTurnRow.created_at.desc())
                .limit(_MAX_HISTORY_TURNS)
                .all()
            )
            conversation_history = [
                {"role": t.role, "content": t.content} for t in reversed(turns)
            ]

        return {
            **state,
            "schema_context": schema_context,
            "dataframes": dataframes,
            "conversation_history": conversation_history,
            "attempts": 0,
            "total_token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0},
        }
    except Exception as exc:  # noqa: BLE001
        log.error("load_context_failed", error=str(exc))
        return {**state, "error": str(exc)}


def classify_intent(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("classify_intent.md")
        prompt = json.dumps({
            "schema": state["schema_context"],
            "conversation_history": state["conversation_history"],
            "question": state["question"],
        })
        text, usage = LLMClient().call_model_with_usage(prompt, system=system)
        decision = _extract_json(text)
        return {
            **state,
            "needs_clarification": bool(decision.get("ambiguous")),
            "clarification_question": decision.get("clarification_question"),
            "total_token_usage": _accumulate_usage(state, usage),
        }
    except Exception as exc:  # noqa: BLE001
        log.error("classify_intent_failed", error=str(exc))
        return {**state, "error": str(exc)}


def generate_code(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("generate_code.md")
        payload = {
            "schema": state["schema_context"],
            "question": state["question"],
        }
        prior_error = (state.get("exec_result") or {}).get("error")
        if prior_error:
            payload["prior_code"] = state.get("generated_code")
            payload["prior_error"] = prior_error

        text, usage = LLMClient().call_model_with_usage(json.dumps(payload), system=system)
        code = _extract_code(text)
        return {
            **state,
            "generated_code": code,
            "attempts": state.get("attempts", 0) + 1,
            "total_token_usage": _accumulate_usage(state, usage),
        }
    except Exception as exc:  # noqa: BLE001
        log.error("generate_code_failed", error=str(exc))
        return {**state, "error": str(exc)}


def execute_code(state: AgentState) -> AgentState:
    settings = get_settings()
    result = sandbox_execute_code(
        state["generated_code"],
        state["dataframes"],
        timeout_seconds=settings.code_exec_timeout_seconds,
    )
    log.info(
        "execute_code",
        attempt=state.get("attempts", 0),
        success=result["error"] is None,
    )
    return {**state, "exec_result": result}


def finalize_answer(state: AgentState) -> AgentState:
    start = time.monotonic()
    try:
        system = _load_prompt("finalize_answer.md")
        exec_result = state["exec_result"]
        prompt = json.dumps({
            "question": state["question"],
            "value": exec_result.get("value"),
            "table_preview": (exec_result.get("table") or [])[:20],
        })
        text, usage = LLMClient().call_model_with_usage(prompt, system=system)
        decision = _extract_json(text)

        table_data = exec_result.get("table")
        chart_spec = None
        if decision.get("chart_type") not in (None, "none") and table_data:
            chart_spec = {
                "type": decision["chart_type"],
                "x_field": decision.get("chart_x_field"),
                "y_field": decision.get("chart_y_field"),
            }

        total_usage = _accumulate_usage(state, usage)
        latency_ms = int((time.monotonic() - start) * 1000)

        with create_db_session() as session:
            turn = ConversationTurnRow(
                session_id=state["session_id"],
                role="assistant",
                content=decision["prose"],
                table_data=table_data,
                chart_spec=chart_spec,
            )
            session.add(turn)
            session.flush()
            session.add(AuditLogEntryRow(
                session_id=state["session_id"],
                turn_id=turn.id,
                question=state["question"],
                generated_code=state.get("generated_code"),
                exec_status="success",
                result_summary=decision["prose"][:500],
                latency_ms=latency_ms,
            ))
            turn_id = turn.id

        return {
            **state,
            "final_answer": decision["prose"],
            "table_data": table_data,
            "chart_spec": chart_spec,
            "total_token_usage": total_usage,
            "status": "completed",
            "_turn_id": turn_id,
        }
    except Exception as exc:  # noqa: BLE001
        log.error("finalize_answer_failed", error=str(exc))
        return {**state, "error": str(exc)}


def handle_clarification(state: AgentState) -> AgentState:
    latency_ms = 0
    with create_db_session() as session:
        turn = ConversationTurnRow(
            session_id=state["session_id"],
            role="assistant",
            content=state["clarification_question"],
        )
        session.add(turn)
        session.flush()
        session.add(AuditLogEntryRow(
            session_id=state["session_id"],
            turn_id=turn.id,
            question=state["question"],
            generated_code=None,
            exec_status="clarification",
            result_summary=state["clarification_question"],
            latency_ms=latency_ms,
        ))
        turn_id = turn.id

    return {
        **state,
        "final_answer": state["clarification_question"],
        "table_data": None,
        "chart_spec": None,
        "status": "completed",
        "_turn_id": turn_id,
    }


def handle_error(state: AgentState) -> AgentState:
    error = state.get("error") or (state.get("exec_result") or {}).get("error") or "unknown error"
    log.error("agent_run_failed", session_id=state.get("session_id"), error=error)

    message = "Sorry, I couldn't complete that analysis. Please try rephrasing or asking something simpler."
    turn_id = None
    try:
        with create_db_session() as session:
            session.add(AuditLogEntryRow(
                session_id=state["session_id"],
                turn_id=None,
                question=state.get("question", ""),
                generated_code=state.get("generated_code"),
                exec_status="error",
                result_summary=error[:500],
                latency_ms=0,
            ))
    except Exception:  # noqa: BLE001
        pass  # audit-log write is best-effort in the terminal error path

    return {**state, "status": "failed", "final_answer": message, "_turn_id": turn_id}
