"""Function Calling: ações e consultas que o copiloto pode disparar."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from src.core.exceptions import DomainError
from src.modules.accounts.services import AccountsService
from src.modules.copilot_chat.store import ConversationStore
from src.modules.market_intelligence.services import MarketIntelligenceService
from src.modules.portfolio.models import Holding
from src.modules.portfolio.services import PortfolioService
from src.modules.scheduling.models import (
    ContextAnswer,
    MeetingContext,
    MeetingRequest,
    TimeSlot,
)
from src.modules.scheduling.services import LOCAL_TZ, SchedulingService

# O que o copiloto precisa saber antes de marcar uma reunião. O assessor lê estas respostas.
INTAKE_QUESTIONS: dict[str, str] = {
    "motivo": "Qual é o assunto principal que você quer tratar na reunião?",
    "objetivo": "O que você espera sair da reunião (uma decisão, um plano, um esclarecimento)?",
    "prazo": "Existe alguma urgência ou prazo (vencimento, evento, valor a movimentar)?",
    "mudancas": "Houve alguma mudança recente na sua vida ou nas suas finanças que devemos saber?",
}
INTAKE_LABELS: dict[str, str] = {
    "motivo": "Assunto",
    "objetivo": "Expectativa",
    "prazo": "Prazo",
    "mudancas": "Mudanças recentes",
}
MAX_TOPIC_LENGTH = 80
SLOT_CHOICES = 8


def build_meeting_context(answers: dict[str, ContextAnswer]) -> MeetingContext:
    ordered = [answers[k] for k in INTAKE_QUESTIONS if k in answers]
    summary = "\n".join(f"{INTAKE_LABELS[a.key]}: {a.answer}" for a in ordered)
    return MeetingContext(answers=ordered, summary=summary)


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _tool(
        "get_portfolio_summary",
        "Resume a carteira do cliente: patrimônio total, alocação por classe e maiores posições.",
        {},
        [],
    ),
    _tool(
        "get_relevant_news",
        "Notícias recentes que citam ativos da carteira do cliente.",
        {},
        [],
    ),
    _tool(
        "get_free_slots",
        "Horários livres do assessor do cliente, do mais próximo ao mais distante.",
        {},
        [],
    ),
    _tool(
        "save_meeting_context",
        "Registra o que o cliente respondeu às perguntas de contexto da reunião. Preencha só os "
        "campos que o cliente realmente respondeu, resumindo com fidelidade; pode registrar vários "
        "de uma vez. Não invente nem deixe campos vazios.",
        {
            key: {"type": "string", "description": f"Resposta do cliente a: {question}"}
            for key, question in INTAKE_QUESTIONS.items()
        },
        [],
    ),
    _tool(
        "schedule_meeting",
        "Marca a reunião com o assessor. Só funciona depois que as quatro respostas de contexto "
        "foram registradas com save_meeting_context.",
        {
            "topic": {"type": "string", "description": "Pauta curta da reunião."},
            "slot_start": {
                "type": "string",
                "description": "Início (ISO 8601) de um horário devolvido por get_free_slots. "
                "Omita para usar o primeiro livre.",
            },
        },
        ["topic"],
    ),
]


class CopilotTools:
    def __init__(
        self,
        scheduling: SchedulingService,
        accounts: AccountsService,
        portfolio: PortfolioService,
        market: MarketIntelligenceService,
        store: ConversationStore,
    ) -> None:
        self._scheduling = scheduling
        self._accounts = accounts
        self._portfolio = portfolio
        self._market = market
        self._store = store

    def missing_context(self, client_id: int) -> list[str]:
        answered = self._store.intake(client_id)
        return [k for k in INTAKE_QUESTIONS if k not in answered]

    def run(self, client_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Executa uma tool a pedido do modelo. O cliente vem da sessão, nunca dos argumentos."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return {"status": "error", "message": f"Ferramenta desconhecida: {name}"}
        try:
            return handler(client_id, **arguments)
        except DomainError as exc:
            return {"status": "error", "message": exc.message}
        except TypeError as exc:
            return {"status": "error", "message": f"Argumentos inválidos: {exc}"}

    # --- consultas -----------------------------------------------------------------

    def _holdings(self, client_id: int) -> list[Holding]:
        portfolio = self._portfolio.get_unified_portfolio(client_id)
        return [*portfolio.internal_holdings, *(h for a in portfolio.external_accounts for h in a.holdings)]

    def _tool_get_portfolio_summary(self, client_id: int) -> dict[str, Any]:
        portfolio = self._portfolio.get_unified_portfolio(client_id)
        holdings = self._holdings(client_id)
        by_class: dict[str, Decimal] = defaultdict(Decimal)
        for h in holdings:
            by_class[h.asset_class.value] += h.market_value
        cash = sum((a.balance for a in portfolio.external_accounts), Decimal(0))
        total = portfolio.total_net_worth
        return {
            "total_net_worth": str(total),
            "external_cash": str(cash),
            "allocation": [
                {
                    "asset_class": cls,
                    "value": str(value),
                    "share_pct": round(float(value / total * 100), 1) if total else 0,
                }
                for cls, value in sorted(by_class.items(), key=lambda kv: kv[1], reverse=True)
            ],
            "top_holdings": [
                {"ticker": h.ticker, "value": str(h.market_value)}
                for h in sorted(holdings, key=lambda h: h.market_value, reverse=True)[:5]
            ],
        }

    def _tool_get_relevant_news(self, client_id: int) -> dict[str, Any]:
        tickers = [h.ticker for h in self._holdings(client_id)]
        return {
            "news": [
                {"title": n.title, "summary": n.summary, "sentiment": n.sentiment.value, "tickers": n.related_tickers}
                for n in self._market.list_news(tickers)
            ]
        }

    def _tool_get_free_slots(self, client_id: int) -> dict[str, Any]:
        advisor_id = self._accounts.get_client(client_id).advisor_id
        slots = self._scheduling.find_free_slots(advisor_id, limit=SLOT_CHOICES)
        return {"slots": [{"start": s.start.isoformat(), "end": s.end.isoformat()} for s in slots]}

    # --- ações ---------------------------------------------------------------------

    def _tool_save_meeting_context(self, client_id: int, **answers: Any) -> dict[str, Any]:
        unknown = [k for k in answers if k not in INTAKE_QUESTIONS]
        if unknown:
            return {"status": "error", "message": f"Campos desconhecidos: {', '.join(unknown)}"}
        saved = []
        for key, value in answers.items():
            text = value.strip() if isinstance(value, str) else ""
            if text:
                self._store.save_answer(
                    client_id, ContextAnswer(key=key, question=INTAKE_QUESTIONS[key], answer=text)
                )
                saved.append(key)
        if not saved:
            return {"status": "error", "message": "Nenhuma resposta preenchida", "missing": self.missing_context(client_id)}
        return {"status": "saved", "saved": saved, "missing": self.missing_context(client_id)}

    def _tool_schedule_meeting(
        self, client_id: int, topic: str, slot_start: str | None = None
    ) -> dict[str, Any]:
        missing = self.missing_context(client_id)
        if missing:
            return {
                "status": "missing_context",
                "message": "Ainda faltam respostas do cliente. Pergunte e registre antes de marcar.",
                "missing": [{"key": k, "question": INTAKE_QUESTIONS[k]} for k in missing],
            }
        advisor_id = self._accounts.get_client(client_id).advisor_id
        answers = self._store.intake(client_id)
        preferred = self._pick_slot(advisor_id, slot_start)
        meeting = self._scheduling.schedule(
            MeetingRequest(
                client_id=client_id,
                advisor_id=advisor_id,
                preferred=preferred,
                topic=(topic.strip() or answers["motivo"].answer)[:MAX_TOPIC_LENGTH],
                context=build_meeting_context(answers),
            )
        )
        self._store.clear_intake(client_id)
        return {"status": "scheduled", "meeting": meeting.model_dump(mode="json")}

    def _pick_slot(self, advisor_id: int, slot_start: str | None) -> TimeSlot | None:
        if not slot_start:
            return None
        try:
            wanted = datetime.fromisoformat(slot_start)
        except ValueError:
            raise DomainError("Horário inválido: use um dos devolvidos por get_free_slots") from None
        wanted = wanted if wanted.tzinfo else wanted.replace(tzinfo=LOCAL_TZ)
        for slot in self._scheduling.find_free_slots(advisor_id, limit=50):
            if slot.start == wanted:
                return slot
        raise DomainError("Esse horário não está livre; escolha outro de get_free_slots")

    def _tool_update_portfolio(self, client_id: int, **changes: Any) -> dict[str, Any]:
        return {"status": "not_implemented", "client_id": client_id}  # TODO
