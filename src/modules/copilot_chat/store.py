"""Memória da conversa e do contexto coletado, em memória até o chat usar a tabela chat_messages."""
import threading

from src.modules.copilot_chat.models import ChatHistoryItem
from src.modules.scheduling.models import ContextAnswer


class ConversationStore:
    def __init__(self) -> None:
        self._history: dict[int, list[ChatHistoryItem]] = {}
        # Respostas às perguntas de contexto, por cliente, ainda não ligadas a nenhuma reunião.
        self._intake: dict[int, dict[str, ContextAnswer]] = {}
        self._lock = threading.Lock()

    def history(self, client_id: int) -> list[ChatHistoryItem]:
        with self._lock:
            return list(self._history.get(client_id, []))

    def append(self, client_id: int, item: ChatHistoryItem) -> None:
        with self._lock:
            self._history.setdefault(client_id, []).append(item)

    def intake(self, client_id: int) -> dict[str, ContextAnswer]:
        with self._lock:
            return dict(self._intake.get(client_id, {}))

    def save_answer(self, client_id: int, answer: ContextAnswer) -> None:
        with self._lock:
            self._intake.setdefault(client_id, {})[answer.key] = answer

    def clear_intake(self, client_id: int) -> None:
        with self._lock:
            self._intake.pop(client_id, None)


_store = ConversationStore()


def get_conversation_store() -> ConversationStore:
    return _store
