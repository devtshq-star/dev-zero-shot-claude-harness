from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import ConversationSessionRow, ConversationTurnRow, DatasetRow
from db.session import get_session
from domain.session import (
    SessionCreateRequest,
    SessionResponse,
    SessionDetailResponse,
    TurnResponse,
    MessageRequest,
    MessageResponse,
    TokenUsage,
)
from graph.runner import run_agent

router = APIRouter()


@router.post("/sessions")
def create_session(req: SessionCreateRequest, session: Session = Depends(get_session)) -> dict:
    if not req.dataset_ids:
        raise api_error("INVALID_REQUEST", "dataset_ids must not be empty", 400)
    for dataset_id in req.dataset_ids:
        if session.get(DatasetRow, dataset_id) is None:
            raise api_error("NOT_FOUND", f"Dataset {dataset_id} not found", 400)

    conv_session = ConversationSessionRow(dataset_ids=req.dataset_ids)
    session.add(conv_session)
    session.flush()
    return ok(_to_response(conv_session).model_dump(mode="json"))


@router.get("/sessions")
def list_sessions(session: Session = Depends(get_session)) -> dict:
    sessions = session.query(ConversationSessionRow).order_by(ConversationSessionRow.last_active_at.desc()).all()
    return ok([_to_response(s).model_dump(mode="json") for s in sessions])


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, session: Session = Depends(get_session)) -> dict:
    conv_session = session.get(ConversationSessionRow, session_id)
    if conv_session is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    turns = (
        session.query(ConversationTurnRow)
        .filter(ConversationTurnRow.session_id == session_id)
        .order_by(ConversationTurnRow.created_at.asc())
        .all()
    )
    detail = SessionDetailResponse(
        id=conv_session.id,
        dataset_ids=conv_session.dataset_ids,
        created_at=conv_session.created_at,
        last_active_at=conv_session.last_active_at,
        turns=[
            TurnResponse(
                id=t.id, role=t.role, content=t.content,
                table_data=t.table_data, chart_spec=t.chart_spec, created_at=t.created_at,
            )
            for t in turns
        ],
    )
    return ok(detail.model_dump(mode="json"))


@router.post("/sessions/{session_id}/messages")
def post_message(session_id: str, req: MessageRequest, session: Session = Depends(get_session)) -> dict:
    if not req.question.strip():
        raise api_error("INVALID_REQUEST", "question must not be empty", 400)
    if session.get(ConversationSessionRow, session_id) is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    # Persist the user's turn before running the agent, so it's in the
    # conversation history for context on the very next question.
    user_turn = ConversationTurnRow(session_id=session_id, role="user", content=req.question)
    session.add(user_turn)
    session.flush()
    session.commit()

    try:
        result = run_agent(session_id, req.question)
    except Exception as exc:  # noqa: BLE001
        raise api_error("ANALYSIS_FAILED", str(exc), 502)

    response = MessageResponse(
        turn_id=result["turn_id"] or user_turn.id,
        role="assistant",
        content=result["content"] or "Sorry, something went wrong answering that.",
        table_data=result["table_data"],
        chart_spec=result["chart_spec"],
        needs_clarification=result["needs_clarification"],
        token_usage=TokenUsage(**result["token_usage"]),
    )
    return ok(response.model_dump(mode="json"))


def _to_response(conv_session: ConversationSessionRow) -> SessionResponse:
    return SessionResponse(
        id=conv_session.id,
        dataset_ids=conv_session.dataset_ids,
        created_at=conv_session.created_at,
        last_active_at=conv_session.last_active_at,
    )
