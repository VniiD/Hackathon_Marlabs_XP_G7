import json
from datetime import datetime
from typing import Any

from fastapi import Depends

from src.core.config import Settings, get_settings
from src.core.exceptions import DomainError
from src.modules.accounts.services import AccountsService, get_accounts_service
from src.modules.copilot_chat.llm import LLMClient, OpenAIClient
from src.modules.copilot_chat.models import (
    ChatHistoryItem,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ToolCall,
)
from src.modules.copilot_chat.store import ConversationStore, get_conversation_store
from src.modules.copilot_chat.tools import INTAKE_QUESTIONS, TOOL_SCHEMAS, CopilotTools
from src.modules.market_intelligence.services import MarketIntelligenceService, get_market_service
from src.modules.portfolio.services import PortfolioService, get_portfolio_service
from src.modules.scheduling.models import ContextAnswer
from src.modules.scheduling.services import LOCAL_TZ, SchedulingService, get_scheduling_service

MAX_TOOL_ROUNDS = 8  # quatro respostas, horários e agendamento, mesmo uma chamada por rodada
HISTORY_WINDOW = 30  # últimas falas enviadas ao modelo
FALLBACK_REPLY = "Não consegui concluir agora. Pode repetir, por favor?"

SYSTEM_PROMPT = """\
Você é o copiloto da plataforma de assessoria financeira, conversando em português do Brasil com \
{name}, cliente com perfil de risco {risk}. Seja cordial, direto e curto (no máximo 3 frases por \
resposta, sem listas longas). Você NÃO dá recomendação de investimento: quando o assunto for \
decidir onde aplicar, sugira conversar com o assessor.

Consulte a carteira e as notícias com as ferramentas antes de falar de números; nunca invente \
valores, ativos ou horários.

REUNIÃO COM O ASSESSOR. Para marcar, é obrigatório coletar as quatro respostas listadas abaixo (e só elas: horário NÃO é uma pergunta de contexto). Pergunte só o que FALTA, na ordem da lista, no máximo duas por vez, de forma natural, sem repetir o que o cliente já disse. Assim que o cliente responder, registre com save_meeting_context (pode ser várias respostas numa chamada) e nunca preencha uma resposta por conta própria. Se uma ferramenta devolver erro, corrija os argumentos e tente de novo; não diga ao cliente que houve erro técnico. Quando as quatro estiverem registradas, chame get_free_slots e schedule_meeting na mesma hora, sem pedir mais nada: use o horário que o cliente pediu, se houver, senão o primeiro livre. Ao marcar, diga o horário e que a reunião só vale depois que a assessoria confirmar.

Contexto da reunião ({done}/{total} respondidas):
{intake}
Hoje é {today}.
"""


def _intake_state(answered: dict[str, ContextAnswer]) -> str:
    lines = []
    for key, question in INTAKE_QUESTIONS.items():
        if key in answered:
            lines.append(f"- {key}: JÁ RESPONDIDO ({answered[key].answer})")
        else:
            lines.append(f"- {key}: FALTA. Pergunta sugerida: {question}")
    return "\n".join(lines)


class CopilotChatService:
    def __init__(
        self,
        llm: LLMClient,
        tools: CopilotTools,
        accounts: AccountsService,
        store: ConversationStore,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._accounts = accounts
        self._store = store

    def history(self, client_id: int) -> list[ChatHistoryItem]:
        self._accounts.get_client(client_id)
        return self._store.history(client_id)

    def handle(self, req: ChatRequest) -> ChatResponse:
        message = req.message.strip()
        if not message:
            raise DomainError("Mensagem vazia")
        client = self._accounts.get_client(req.client_id)

        past = self._store.history(req.client_id)[-HISTORY_WINDOW:]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt(req.client_id, client.user.name, client.risk_profile.value)},
            *({"role": "user" if h.role == ChatRole.USER else "assistant", "content": h.content} for h in past),
            {"role": "user", "content": message},
        ]

        surfaced: list[ToolCall] = []
        reply = FALLBACK_REPLY
        for _ in range(MAX_TOOL_ROUNDS):
            answer = self._llm.chat(messages, TOOL_SCHEMAS)
            if not answer.tool_calls:
                reply = (answer.content or "").strip() or FALLBACK_REPLY
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": answer.content,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": _dump(c.arguments)},
                        }
                        for c in answer.tool_calls
                    ],
                }
            )
            for call in answer.tool_calls:
                result = self._tools.run(req.client_id, call.name, call.arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": _dump(result)})
                if call.name == "schedule_meeting" and result.get("status") == "scheduled":
                    meeting = result["meeting"]
                    surfaced.append(
                        ToolCall(
                            name="schedule_meeting",
                            arguments={
                                "client_id": meeting["client_id"],
                                "advisor_id": meeting["advisor_id"],
                                "meeting_id": meeting["id"],
                            },
                        )
                    )
        # Só grava depois de dar certo, para uma falha da OpenAI não deixar uma pergunta sem resposta.
        self._store.append(req.client_id, ChatHistoryItem(role=ChatRole.USER, content=message))
        self._store.append(
            req.client_id, ChatHistoryItem(role=ChatRole.ASSISTANT, content=reply, tool_calls=surfaced)
        )
        return ChatResponse(reply=reply, tool_calls=surfaced)

    def _system_prompt(self, client_id: int, name: str, risk: str) -> str:
        answered = self._store.intake(client_id)
        return SYSTEM_PROMPT.format(
            name=name,
            risk=risk.lower(),
            done=len(answered),
            total=len(INTAKE_QUESTIONS),
            intake=_intake_state(answered),
            today=datetime.now(LOCAL_TZ).strftime("%d/%m/%Y"),
        )


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    return OpenAIClient(settings)


def get_copilot_service(
    llm: LLMClient = Depends(get_llm_client),
    accounts: AccountsService = Depends(get_accounts_service),
    scheduling: SchedulingService = Depends(get_scheduling_service),
    portfolio: PortfolioService = Depends(get_portfolio_service),
    market: MarketIntelligenceService = Depends(get_market_service),
    store: ConversationStore = Depends(get_conversation_store),
) -> CopilotChatService:
    tools = CopilotTools(scheduling, accounts, portfolio, market, store)
    return CopilotChatService(llm, tools, accounts, store)
