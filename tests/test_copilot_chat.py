import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.core.config import Settings
from src.core.exceptions import ExternalServiceError, ForbiddenError
from src.main import app
from src.core.exceptions import NotFoundError
from src.modules.accounts.models import ClientCreate, ClientProfile, RiskProfile, User, UserRole
from src.modules.advisor_dashboard.engine import DailyAdvisorEngine
from src.modules.advisor_dashboard.services import AdvisorDashboardService, _points_cache
from src.modules.copilot_chat.llm import LLMMessage, LLMToolCall, OpenAIClient
from src.modules.copilot_chat.models import ChatRequest
from src.modules.copilot_chat.services import CopilotChatService, get_copilot_service
from src.modules.copilot_chat.store import ConversationStore
from src.modules.copilot_chat.tools import INTAKE_QUESTIONS, CopilotTools
from src.modules.market_intelligence.services import MarketIntelligenceService
from src.modules.portfolio.models import AssetClass, Holding
from src.modules.portfolio.open_finance import OpenFinanceIntegrationService
from src.modules.portfolio.services import PortfolioService
from src.modules.scheduling.services import SchedulingService

ADVISOR = 1
ANSWERS = {
    "motivo": "Meu CDB vence este mês",
    "objetivo": "Decidir onde reaplicar",
    "prazo": "Vence em 9 dias",
    "mudancas": "Vou comprar um apartamento",
}


class FakeAccounts:
    """AccountsService em memória: o de verdade lê clientes do Postgres, que estes testes dispensam."""

    def __init__(self) -> None:
        self._clients: dict[int, ClientProfile] = {}

    def create_client(self, data: ClientCreate) -> ClientProfile:
        client_id = len(self._clients) + 1
        user = User(id=client_id, name=data.name, email=data.email, role=UserRole.CLIENT)
        profile = ClientProfile(
            user=user, advisor_id=data.advisor_id, risk_profile=data.risk_profile, context=data.context
        )
        self._clients[client_id] = profile
        return profile

    def get_client(self, client_id: int) -> ClientProfile:
        if client_id not in self._clients:
            raise NotFoundError(f"Cliente {client_id} não encontrado")
        return self._clients[client_id]


class FakeLLM:
    """Responde com mensagens roteirizadas e guarda o que recebeu."""

    def __init__(self, *script: LLMMessage | Exception) -> None:
        self._script = list(script)
        self.received: list[list[dict]] = []

    def chat(self, messages, tools):
        self.received.append(json.loads(json.dumps(messages)))
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _call(name: str, **arguments) -> LLMMessage:
    return LLMMessage(tool_calls=[LLMToolCall(id=f"call-{name}", name=name, arguments=arguments)])


def _text(content: str) -> LLMMessage:
    return LLMMessage(content=content)


def _save_all() -> list[LLMMessage]:
    return [_call("save_meeting_context", **ANSWERS)]


@pytest.fixture
def world():
    accounts = FakeAccounts()
    client = accounts.create_client(
        ClientCreate(name="Camila Prates", email="c@x.com", advisor_id=ADVISOR, risk_profile=RiskProfile.CONSERVADOR)
    )
    scheduling = SchedulingService()
    portfolio = PortfolioService(OpenFinanceIntegrationService(Settings()))
    portfolio.set_internal_holdings(
        client.user.id,
        [
            Holding(ticker="CDB-XP-2026", asset_class=AssetClass.RENDA_FIXA, quantity=Decimal(1), market_value=Decimal("180000")),
            Holding(ticker="ITUB4", asset_class=AssetClass.ACOES, quantity=Decimal(100), market_value=Decimal("20000")),
        ],
    )
    return {
        "client_id": client.user.id,
        "accounts": accounts,
        "scheduling": scheduling,
        "portfolio": portfolio,
        "market": MarketIntelligenceService(redis=None),  # type: ignore[arg-type]
        "store": ConversationStore(),
    }


def _chat(world, llm: FakeLLM) -> CopilotChatService:
    tools = CopilotTools(world["scheduling"], world["accounts"], world["portfolio"], world["market"], world["store"])
    return CopilotChatService(llm, tools, world["accounts"], world["store"])


def _say(svc: CopilotChatService, world, text: str):
    return svc.handle(ChatRequest(client_id=world["client_id"], message=text))


def test_schedule_is_refused_until_context_is_collected(world):
    llm = FakeLLM(_call("schedule_meeting", topic="Conversar"), _text("Antes, qual é o assunto?"))
    svc = _chat(world, llm)

    res = _say(svc, world, "Quero marcar uma reunião")

    assert res.reply == "Antes, qual é o assunto?" and res.tool_calls == []
    assert world["scheduling"].list_for_client(world["client_id"]) == []
    tool_message = next(m for m in llm.received[1] if m["role"] == "tool")
    result = json.loads(tool_message["content"])
    assert result["status"] == "missing_context"
    assert {m["key"] for m in result["missing"]} == set(INTAKE_QUESTIONS)


def test_meeting_is_scheduled_with_the_collected_context(world):
    llm = FakeLLM(*_save_all(), _call("schedule_meeting", topic="CDB que vence"), _text("Marquei!"))
    svc = _chat(world, llm)

    res = _say(svc, world, "Respondi tudo, pode marcar")

    assert [t.name for t in res.tool_calls] == ["schedule_meeting"]
    (meeting,) = world["scheduling"].list_for_client(world["client_id"])
    assert meeting.advisor_id == ADVISOR and meeting.topic == "CDB que vence"
    assert [a.answer for a in meeting.context.answers] == list(ANSWERS.values())
    assert meeting.context.summary.startswith("Assunto: Meu CDB vence este mês")
    assert world["store"].intake(world["client_id"]) == {}  # o contexto foi consumido


def test_one_answer_missing_still_blocks_the_meeting(world):
    partial = _call("save_meeting_context", **dict(list(ANSWERS.items())[:3]))
    llm = FakeLLM(partial, _call("schedule_meeting", topic="x"), _text("Falta um detalhe"))
    svc = _chat(world, llm)

    _say(svc, world, "marque")

    assert world["scheduling"].list_for_client(world["client_id"]) == []
    assert list(world["store"].intake(world["client_id"])) == ["motivo", "objetivo", "prazo"]


def test_unknown_slot_is_not_booked(world):
    llm = FakeLLM(*_save_all(), _call("schedule_meeting", topic="x", slot_start="2031-01-01T03:00:00-03:00"), _text("Esse não dá"))
    svc = _chat(world, llm)

    res = _say(svc, world, "marque às 3h")

    assert res.tool_calls == []
    assert world["scheduling"].list_for_client(world["client_id"]) == []
    assert world["store"].intake(world["client_id"])  # as respostas continuam guardadas


def test_history_is_kept_and_sent_back_to_the_model(world):
    llm = FakeLLM(_text("Olá!"), _text("Tudo bem."))
    svc = _chat(world, llm)

    _say(svc, world, "oi")
    _say(svc, world, "como vai?")

    assert [(h.role.value, h.content) for h in svc.history(world["client_id"])] == [
        ("USER", "oi"),
        ("ASSISTANT", "Olá!"),
        ("USER", "como vai?"),
        ("ASSISTANT", "Tudo bem."),
    ]
    second_call = llm.received[1]
    assert [m["content"] for m in second_call[1:]] == ["oi", "Olá!", "como vai?"]
    assert "Camila Prates" in second_call[0]["content"]


def test_failed_llm_call_leaves_no_dangling_message(world):
    svc = _chat(world, FakeLLM(ExternalServiceError("A OpenAI não respondeu")))
    with pytest.raises(ExternalServiceError):
        _say(svc, world, "oi")
    assert svc.history(world["client_id"]) == []


def test_tools_read_portfolio_and_news(world):
    tools = CopilotTools(world["scheduling"], world["accounts"], world["portfolio"], world["market"], world["store"])
    summary = tools.run(world["client_id"], "get_portfolio_summary", {})
    assert summary["total_net_worth"] == "200000" and summary["allocation"][0]["asset_class"] == "RENDA_FIXA"
    news = tools.run(world["client_id"], "get_relevant_news", {})["news"]
    assert [n["tickers"] for n in news] == [["ITUB4"], ["TESOURO-SELIC-2029", "CDB-XP-2026"]]
    assert tools.run(world["client_id"], "nao_existe", {})["status"] == "error"


def test_without_api_key_the_chat_answers_502(world):
    svc = CopilotChatService(
        OpenAIClient(Settings(openai_api_key="")),
        CopilotTools(world["scheduling"], world["accounts"], world["portfolio"], world["market"], world["store"]),
        world["accounts"],
        world["store"],
    )
    app.dependency_overrides[get_copilot_service] = lambda: svc
    try:
        res = TestClient(app).post("/api/v1/copilot/chat", json={"client_id": world["client_id"], "message": "oi"})
        assert res.status_code == 502 and "OPENAI_API_KEY" in res.json()["detail"]
        assert TestClient(app).get(f"/api/v1/copilot/chat/{world['client_id']}/history").json() == []
    finally:
        app.dependency_overrides.clear()


def _dashboard(world, llm: FakeLLM) -> AdvisorDashboardService:
    return AdvisorDashboardService(
        world["accounts"], world["portfolio"], DailyAdvisorEngine(), world["scheduling"], world["market"], llm
    )


def _book_with_context(world):
    llm = FakeLLM(*_save_all(), _call("schedule_meeting", topic="CDB que vence"), _text("ok"))
    _say(_chat(world, llm), world, "marque")
    return world["scheduling"].list_for_client(world["client_id"])[0]


def test_briefing_combines_context_portfolio_and_news(world):
    _points_cache.clear()
    meeting = _book_with_context(world)
    llm = FakeLLM(_text("- Falar do CDB que vence\n- ITUB4 caiu hoje\n"))

    briefing = _dashboard(world, llm).build_briefing(ADVISOR, meeting.id)

    assert briefing.client_name == "Camila Prates"
    assert briefing.context.answers[0].answer == ANSWERS["motivo"]
    assert briefing.portfolio.total_net_worth == Decimal("200000")
    assert briefing.portfolio.allocation[0].share_pct == 90.0
    assert [n.related_tickers for n in briefing.news] == [["ITUB4"], ["TESOURO-SELIC-2029", "CDB-XP-2026"]]
    assert briefing.talking_points == ["Falar do CDB que vence", "ITUB4 caiu hoje"]
    prompt = llm.received[0][0]["content"]
    assert ANSWERS["prazo"] in prompt and "ITUB4" in prompt


def test_briefing_falls_back_when_the_llm_is_down(world):
    _points_cache.clear()
    meeting = _book_with_context(world)

    briefing = _dashboard(world, FakeLLM(ExternalServiceError("fora do ar"))).build_briefing(ADVISOR, meeting.id)

    assert any(ANSWERS["motivo"] in p for p in briefing.talking_points)
    assert any("Notícia para comentar" in p for p in briefing.talking_points)


def test_briefing_is_only_for_the_meetings_advisor(world):
    meeting = _book_with_context(world)
    with pytest.raises(ForbiddenError):
        _dashboard(world, FakeLLM()).build_briefing(ADVISOR + 1, meeting.id)


def test_openai_client_parses_tool_calls_and_wraps_errors(monkeypatch):
    from types import SimpleNamespace

    import openai

    seen = {}

    def completion(**kwargs):
        seen.update(kwargs)
        call = SimpleNamespace(
            id="c1", type="function", function=SimpleNamespace(name="schedule_meeting", arguments='{"topic": "x"}')
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
    monkeypatch.setattr(openai, "OpenAI", lambda **_: fake)
    client = OpenAIClient(Settings(openai_api_key="sk-test", openai_model="m"))

    message = client.chat([{"role": "user", "content": "oi"}], [])
    assert message.tool_calls == [LLMToolCall(id="c1", name="schedule_meeting", arguments={"topic": "x"})]
    assert seen["model"] == "m" and seen["tools"] is openai.NOT_GIVEN

    def boom(**_):
        raise openai.APIConnectionError(request=None)  # type: ignore[arg-type]

    fake.chat.completions.create = boom
    with pytest.raises(ExternalServiceError):
        client.chat([], [])


def test_save_context_accepts_one_answer_at_a_time_and_rejects_bad_input(world):
    tools = CopilotTools(world["scheduling"], world["accounts"], world["portfolio"], world["market"], world["store"])
    client_id = world["client_id"]

    first = tools.run(client_id, "save_meeting_context", {"motivo": " CDB vencendo ", "prazo": ""})
    assert first == {"status": "saved", "saved": ["motivo"], "missing": ["objetivo", "prazo", "mudancas"]}
    assert world["store"].intake(client_id)["motivo"].answer == "CDB vencendo"

    assert tools.run(client_id, "save_meeting_context", {"humor": "bom"})["status"] == "error"
    assert tools.run(client_id, "save_meeting_context", {})["status"] == "error"
    assert list(world["store"].intake(client_id)) == ["motivo"]
