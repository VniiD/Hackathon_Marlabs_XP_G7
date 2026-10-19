"""Cliente de LLM do copiloto. A interface existe para os testes injetarem um fake."""
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import openai

from src.core.config import Settings
from src.core.exceptions import ExternalServiceError

REQUEST_TIMEOUT_SECONDS = 45


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMMessage:
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMMessage: ...


class OpenAIClient:
    """Chat Completions da OpenAI com function calling."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMMessage:
        if not self._api_key:
            raise ExternalServiceError("Chat não configurado: defina OPENAI_API_KEY")
        client = openai.OpenAI(api_key=self._api_key, timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            completion = client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                tools=tools or openai.NOT_GIVEN,  # type: ignore[arg-type]
            )
        except openai.OpenAIError as exc:
            raise ExternalServiceError("A OpenAI não respondeu") from exc
        message = completion.choices[0].message
        calls = [
            LLMToolCall(id=c.id, name=c.function.name, arguments=_parse_arguments(c.function.arguments))
            for c in (message.tool_calls or [])
            if c.type == "function"
        ]
        return LLMMessage(content=message.content, tool_calls=calls)


def _parse_arguments(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
