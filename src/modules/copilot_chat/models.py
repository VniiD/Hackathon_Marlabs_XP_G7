from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    client_id: int
    message: str  # texto ou transcrição de voz


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCall] = []


class ChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ChatHistoryItem(BaseModel):
    """Uma fala da conversa; mesmos papéis da tabela chat_messages."""

    role: ChatRole
    content: str
    tool_calls: list[ToolCall] = []


class Transcript(BaseModel):
    text: str
    duration_seconds: float
