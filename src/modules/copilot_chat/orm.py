"""Histórico do copiloto — serve de memória da conversa enviada ao Gemini."""

import datetime as dt
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ChatMessageRecord(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.user_id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text)  # USER | ASSISTANT
    content: Mapped[str] = mapped_column(Text)  # texto ou transcrição da voz
    input_mode: Mapped[str] = mapped_column(Text, default="TEXT")  # TEXT | VOICE
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)  # [ToolCall.model_dump()]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
