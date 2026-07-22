from datetime import datetime

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    dataset_ids: list[str]


class SessionResponse(BaseModel):
    id: str
    dataset_ids: list[str]
    created_at: datetime
    last_active_at: datetime


class TurnResponse(BaseModel):
    id: str
    role: str
    content: str
    table_data: list[dict] | None = None
    chart_spec: dict | None = None
    follow_ups: list[str] = []
    created_at: datetime


class SessionDetailResponse(SessionResponse):
    turns: list[TurnResponse]


class MessageRequest(BaseModel):
    question: str
    language: str = "en"  # UI language ("en"|"hi"); preferred agent response language


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float


class MessageResponse(BaseModel):
    turn_id: str
    role: str
    content: str
    table_data: list[dict] | None = None
    chart_spec: dict | None = None
    needs_clarification: bool
    follow_ups: list[str] = []
    token_usage: TokenUsage
