from pydantic import BaseModel
from typing import Any


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = []
    session_id: str = ""
    model: str = "flash"
    project: str = "ccc"
    timeout: int = 600


class SessionData(BaseModel):
    session_id: str
    title: str = "New Chat"
    project: str = "ccc"
    messages: list[dict[str, Any]] = []
    mode: str = "chat"
    created_at: str = ""
    updated_at: str = ""
    status: str = ""
    reply: str = ""
    execution_results: list[dict[str, Any]] = []
    total_cost_usd: float | None = None
