from datetime import datetime, timezone

from db.models import ConversationSessionRow
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.state import AgentState


def run_agent(session_id: str, question: str, language: str = "en") -> dict:
    with create_db_session() as db_session:
        conv_session = db_session.get(ConversationSessionRow, session_id)
        if conv_session is None:
            raise ValueError(f"Session {session_id} not found")
        dataset_ids = list(conv_session.dataset_ids)

    initial: AgentState = {
        "session_id": session_id,
        "dataset_ids": dataset_ids,
        "question": question,
        "language": language,
        "error": None,
    }
    final = agentic_ai.invoke(initial)

    with create_db_session() as db_session:
        conv_session = db_session.get(ConversationSessionRow, session_id)
        conv_session.last_active_at = datetime.now(timezone.utc)

    return {
        "turn_id": final.get("_turn_id"),
        "content": final.get("final_answer"),
        "table_data": final.get("table_data"),
        "chart_spec": final.get("chart_spec"),
        "needs_clarification": bool(final.get("needs_clarification")),
        "follow_ups": final.get("follow_ups") or [],
        "token_usage": final.get("total_token_usage") or {
            "prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0,
        },
    }
