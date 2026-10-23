import json
from datetime import datetime
from decimal import Decimal

import pytest
import httpx2
from redis import Redis
from fastapi.testclient import TestClient

from src.core.config import Settings
from src.core.exceptions import ExternalServiceError, ForbiddenError
from src.main import app
from src.core.exceptions import NotFoundError
from src.modules.accounts.models import (
    ClientCreate,
    ClientProfile,
    PersonalContext,
    RiskProfile,
    User,
    UserRole,
)
from src.modules.advisor_dashboard.engine import DailyAdvisorEngine
from src.modules.advisor_dashboard.services import (
    AdvisorDashboardService,
    _points_cache,
)
from src.modules.copilot_chat.llm import LLMMessage, LLMToolCall, OpenAIClient
from src.modules.copilot_chat.models import ChatRequest
from src.modules.copilot_chat.services import CopilotChatService, get_copilot_service
from src.modules.copilot_chat.store import ConversationStore
from src.modules.copilot_chat.tools import INTAKE_QUESTIONS, CopilotTools
from src.modules.copilot_chat.transcription import get_transcription_service
from src.modules.market_intelligence.models import CurrencyRate, NewsItem, Sentiment
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
        user = User(
            id=client_id, name=data.name, email=data.email, role=UserRole.CLIENT
        )
        profile = ClientProfile(
            user=user,
            advisor_id=data.advisor_id,
            risk_profile=data.risk_profile,
            context=data.context,
        )
        self._clients[client_id] = profile
        return profile

    def get_client(self, client_id: int) -> ClientProfile:
        if client_id not in self._clients:
            raise NotFoundError(f"Cliente {client_id} não encontrado")
        return self._clients[client_id]

    def list_clients_by_advisor(self, advisor_id: int) -> list[ClientProfile]:
        return [
            client
            for client in self._clients.values()
            if client.advisor_id == advisor_id
        ]


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
    return LLMMessage(
        tool_calls=[LLMToolCall(id=f"call-{name}", name=name, arguments=arguments)]
    )


def _text(content: str) -> LLMMessage:
    return LLMMessage(content=content)


def _save_all() -> list[LLMMessage]:
    return [_call("save_meeting_context", **ANSWERS)]


@pytest.fixture
def world():
    accounts = FakeAccounts()
    client = accounts.create_client(
        ClientCreate(
            name="Camila Prates",
            email="c@x.com",
            advisor_id=ADVISOR,
            risk_profile=RiskProfile.CONSERVADOR,
        )
    )
    scheduling = SchedulingService()
    portfolio = PortfolioService(OpenFinanceIntegrationService(Settings()))
    portfolio.set_internal_holdings(
        client.user.id,
        [
            Holding(
                ticker="CDB-XP-2026",
                asset_class=AssetClass.RENDA_FIXA,
                quantity=Decimal(1),
                market_value=Decimal("180000"),
            ),
            Holding(
                ticker="ITUB4",
                asset_class=AssetClass.ACOES,
                quantity=Decimal(100),
                market_value=Decimal("20000"),
            ),
        ],
    )
    return {
        "client_id": client.user.id,
        "accounts": accounts,
        "scheduling": scheduling,
        "portfolio": portfolio,
        "market": MarketIntelligenceService(redis=Redis()),
        "store": ConversationStore(),
    }


def _chat(world, llm: FakeLLM) -> CopilotChatService:
    tools = CopilotTools(
        world["scheduling"],
        world["accounts"],
        world["portfolio"],
        world["market"],
        world["store"],
    )
    return CopilotChatService(llm, tools, world["accounts"], world["store"])


def _say(svc: CopilotChatService, world, text: str):
    return svc.handle(ChatRequest(client_id=world["client_id"], message=text))


def test_schedule_is_refused_until_context_is_collected(world):
    llm = FakeLLM(
        _call("schedule_meeting", topic="Conversar"), _text("Antes, qual é o assunto?")
    )
    svc = _chat(world, llm)

    res = _say(svc, world, "Quero marcar uma reunião")

    assert res.reply == "Antes, qual é o assunto?" and res.tool_calls == []
    assert world["scheduling"].list_for_client(world["client_id"]) == []
    tool_message = next(m for m in llm.received[1] if m["role"] == "tool")
    result = json.loads(tool_message["content"])
    assert result["status"] == "missing_context"
    assert {m["key"] for m in result["missing"]} == set(INTAKE_QUESTIONS)


def test_meeting_is_scheduled_with_the_collected_context(world):
    llm = FakeLLM(
        *_save_all(),
        _call("schedule_meeting", topic="CDB que vence"),
        _text("Marquei!"),
    )
    svc = _chat(world, llm)

    res = _say(svc, world, "Respondi tudo, pode marcar")

    assert [t.name for t in res.tool_calls] == ["schedule_meeting"]
    (meeting,) = world["scheduling"].list_for_client(world["client_id"])
    assert meeting.advisor_id == ADVISOR and meeting.topic == "CDB que vence"
    assert [a.answer for a in meeting.context.answers] == list(ANSWERS.values())
    assert meeting.context.summary.startswith("Assunto: Meu CDB vence este mês")
    assert "resumo do assunto foi encaminhado" in res.reply
    assert "retornará a você" in res.reply
    assert "resumo do assunto foi encaminhado" in res.reply
    assert "retornará a você" in res.reply
    assert world["store"].intake(world["client_id"]) == {}  # o contexto foi consumido


def test_one_answer_missing_still_blocks_the_meeting(world):
    partial = _call("save_meeting_context", **dict(list(ANSWERS.items())[:3]))
    llm = FakeLLM(
        partial, _call("schedule_meeting", topic="x"), _text("Falta um detalhe")
    )
    svc = _chat(world, llm)

    _say(svc, world, "marque")

    assert world["scheduling"].list_for_client(world["client_id"]) == []
    assert list(world["store"].intake(world["client_id"])) == [
        "motivo",
        "objetivo",
        "prazo",
    ]


def test_unknown_slot_is_not_booked(world):
    llm = FakeLLM(
        *_save_all(),
        _call("schedule_meeting", topic="x", slot_start="2031-01-01T03:00:00-03:00"),
        _text("Esse não dá"),
    )
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


def test_failed_llm_call_uses_local_fallback_and_keeps_history(world):
    svc = _chat(world, FakeLLM(ExternalServiceError("A OpenAI não respondeu")))
    response = _say(svc, world, "oi")
    assert "modo local" in response.reply
    assert [item.role.value for item in svc.history(world["client_id"])] == [
        "USER",
        "ASSISTANT",
    ]


def test_tools_read_portfolio_and_news(world):
    tools = CopilotTools(
        world["scheduling"],
        world["accounts"],
        world["portfolio"],
        world["market"],
        world["store"],
    )
    summary = tools.run(world["client_id"], "get_portfolio_summary", {})
    assert (
        summary["total_net_worth"] == "200000"
        and summary["allocation"][0]["asset_class"] == "RENDA_FIXA"
    )
    news = tools.run(world["client_id"], "get_relevant_news", {})["news"]
    assert [n["tickers"] for n in news] == [
        ["ITUB4"],
        ["TESOURO-SELIC-2029", "CDB-XP-2026"],
    ]
    assert tools.run(world["client_id"], "nao_existe", {})["status"] == "error"


def test_local_transcription_returns_text_and_duration():
    from types import SimpleNamespace

    from src.modules.copilot_chat.transcription import TranscriptionService

    class FakeModel:
        def transcribe(self, audio, **options):
            assert audio.read() == b"audio-bytes"
            assert options["language"] == "pt"
            return iter(
                [SimpleNamespace(text=" Olá "), SimpleNamespace(text=" mundo ")]
            ), SimpleNamespace(duration=2.5)

    transcript = TranscriptionService(
        Settings(whisper_model="tiny"), model=FakeModel()
    ).transcribe(b"audio-bytes")

    assert transcript.text == "Olá mundo"
    assert transcript.duration_seconds == 2.5


def test_transcription_route_rejects_oversized_stream(monkeypatch):
    monkeypatch.setattr("src.modules.copilot_chat.router.MAX_AUDIO_BYTES", 8)
    app.dependency_overrides[get_transcription_service] = lambda: object()
    try:
        response = TestClient(app).post(
            "/api/v1/copilot/transcribe", content=b"123456789"
        )
    finally:
        app.dependency_overrides.pop(get_transcription_service, None)

    assert response.status_code == 413


def test_negative_news_impact_matches_exposure_and_changes_priority(world):
    async def fetch_news():
        return [
            NewsItem(
                source="Teste",
                title="ITUB4 cai após revisão",
                published_at=datetime(2026, 10, 22),
                related_tickers=["ITUB4"],
                sentiment=Sentiment.NEGATIVE,
            ),
            NewsItem(
                source="Teste",
                title="PETR4 cai no pregão",
                published_at=datetime(2026, 10, 22),
                related_tickers=["PETR4"],
                sentiment=Sentiment.NEGATIVE,
            ),
        ]

    world["market"].fetch_news = fetch_news

    async def fetch_currency_line():
        return [
            CurrencyRate(
                code="BRL",
                name="Real brasileiro",
                value=Decimal("5.50"),
                variation_pct=Decimal("5.0"),
                updated_at=datetime(2026, 10, 22),
            )
        ]

    world["market"].fetch_currency_line = fetch_currency_line
    llm = FakeLLM(
        _text(
            json.dumps(
                [
                    {
                        "client_id": world["client_id"],
                        "adjustment": 40,
                        "rationale": "Revisão humana prioritária",
                    }
                ]
            )
        )
    )
    dashboard = _dashboard(world, llm)

    impacts = dashboard.news_impact_list(ADVISOR)
    priorities = dashboard.daily_priority_list(ADVISOR)

    assert len(impacts) == 1
    assert impacts[0].related_tickers == ["ITUB4"]
    assert impacts[0].affected_clients[0].exposure_value == Decimal("20000")
    assert impacts[0].affected_clients[0].exposure_pct == 10.0
    assert 20 <= priorities[0].criticality_score < 30
    assert priorities[0].next_best_action.title == "Revisar notícia ligada à carteira"
    assert priorities[0].next_best_action.rationale == "Revisão humana prioritária"
    sent_prompt = llm.received[0][0]["content"]
    assert "BRL variou 5.00%" in sent_prompt


def test_positive_asset_news_still_links_client_exposure_without_penalty(world):
    async def fetch_news():
        return [
            NewsItem(
                source="Teste",
                title="ITUB4 avança após resultado positivo",
                published_at=datetime(2026, 10, 22),
                related_tickers=["ITUB4"],
                sentiment=Sentiment.POSITIVE,
            )
        ]

    world["market"].fetch_news = fetch_news
    dashboard = _dashboard(world, FakeLLM())

    impacts = dashboard.news_impact_list(ADVISOR)

    assert len(impacts) == 1
    assert impacts[0].sentiment == Sentiment.POSITIVE
    assert impacts[0].affected_clients[0].client_id == world["client_id"]


def test_negative_news_reorders_clients_with_the_same_risk_profile(world):
    first_id = world["client_id"]
    first = world["accounts"].get_client(first_id)
    world["accounts"]._clients[first_id] = first.model_copy(
        update={"risk_profile": RiskProfile.MODERADO}
    )
    second = world["accounts"].create_client(
        ClientCreate(
            name="Joao Lima",
            email="j@x.com",
            advisor_id=ADVISOR,
            risk_profile=RiskProfile.MODERADO,
        )
    )
    world["portfolio"].set_internal_holdings(
        second.user.id,
        [
            Holding(
                ticker="ITUB4",
                asset_class=AssetClass.ACOES,
                quantity=Decimal(100),
                market_value=Decimal("50000"),
            ),
            Holding(
                ticker="CDB-XP-2026",
                asset_class=AssetClass.RENDA_FIXA,
                quantity=Decimal(1),
                market_value=Decimal("50000"),
            ),
        ],
    )

    async def fetch_news():
        return [
            NewsItem(
                source="Teste",
                title="ITUB4 cai após revisão",
                published_at=datetime(2026, 10, 22),
                related_tickers=["ITUB4"],
                sentiment=Sentiment.NEGATIVE,
            )
        ]

    world["market"].fetch_news = fetch_news
    priorities = _dashboard(world, FakeLLM()).daily_priority_list(ADVISOR)

    assert [item.client_id for item in priorities] == [second.user.id, first_id]
    assert priorities[0].criticality_score > priorities[1].criticality_score


def test_fixed_income_ticker_is_matched_from_news_description(world):
    async def fetch_news():
        return [
            NewsItem(
                source="Valor Econômico",
                title="Mudanças nas taxas de renda fixa",
                summary="Investidores acompanham o vencimento do CDB-XP-2026.",
                url="https://example.com/mercados/renda-fixa",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.NEUTRAL,
            )
        ]

    world["market"].fetch_news = fetch_news
    impacts = _dashboard(world, FakeLLM()).news_impact_list(ADVISOR)

    assert len(impacts) == 1
    assert impacts[0].related_tickers == ["CDB-XP-2026"]
    assert impacts[0].affected_clients[0].exposure_value == Decimal("180000")


def test_dashboard_shows_market_news_without_claiming_client_exposure(world):
    async def fetch_news():
        return [
            NewsItem(
                source="InfoMoney",
                title="Bolsa fecha em alta após pregão positivo",
                url="https://www.infomoney.com.br/mercados/bolsa-em-alta/",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.POSITIVE,
            ),
            NewsItem(
                source="InfoMoney",
                title="Resultado da loteria",
                url="https://www.infomoney.com.br/consumo/loteria/",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.NEUTRAL,
            ),
        ]

    world["market"].fetch_news = fetch_news
    items = _dashboard(world, FakeLLM()).news_impact_list(ADVISOR)

    assert len(items) == 1
    assert items[0].title == "Bolsa fecha em alta após pregão positivo"
    assert items[0].affected_clients == []


def test_financial_feed_includes_finance_news_but_not_political_corrida(world):
    client_id = world["client_id"]
    client = world["accounts"].get_client(client_id)
    world["accounts"]._clients[client_id] = client.model_copy(
        update={"context": PersonalContext(hobbies=["Corrida"])}
    )

    async def fetch_news():
        return [
            NewsItem(
                source="Valor Econômico",
                title="Fundo imobiliário anuncia nova emissão",
                url="https://valor.globo.com/financas/noticia/fundo.ghtml",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.NEUTRAL,
            ),
            NewsItem(
                source="Valor Econômico",
                title="Datafolha analisa corrida eleitoral",
                summary="Candidatos disputam votos na reta final.",
                url="https://valor.globo.com/politica/eleicoes/corrida.ghtml",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.NEUTRAL,
            ),
        ]

    world["market"].fetch_news = fetch_news
    items = _dashboard(world, FakeLLM()).news_impact_list(ADVISOR)

    assert [item.title for item in items] == ["Fundo imobiliário anuncia nova emissão"]
    assert items[0].interested_clients == []


def test_favorite_team_news_matches_client_with_both_sentiments(world):
    client_id = world["client_id"]
    client = world["accounts"].get_client(client_id)
    world["accounts"]._clients[client_id] = client.model_copy(
        update={
            "context": PersonalContext(favorite_team="Corinthians"),
        }
    )

    async def fetch_news():
        return [
            NewsItem(
                source="Esportes",
                title="Corinthians conquista vitória no clássico",
                url="https://example.com/esportes/corinthians-vitoria",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.POSITIVE,
            ),
            NewsItem(
                source="Esportes",
                title="Timão sofre derrota fora de casa",
                url="https://example.com/esportes/timao-derrota",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.NEGATIVE,
            ),
        ]

    world["market"].fetch_news = fetch_news
    dashboard = _dashboard(world, FakeLLM())
    impacts = dashboard.news_impact_list(ADVISOR)
    priorities = dashboard.daily_priority_list(ADVISOR)

    assert len(impacts) == 2
    assert all(
        news.interested_clients[0].matched_interest == "Corinthians" for news in impacts
    )
    assert [news.interested_clients[0].sentiment for news in impacts] == [
        Sentiment.POSITIVE,
        Sentiment.NEGATIVE,
    ]
    assert all(not news.affected_clients for news in impacts)
    assert priorities[0].criticality_score >= 10
    assert priorities[0].next_best_action.title == (
        "Acompanhar notícia ligada a interesse pessoal"
    )


def test_favorite_team_news_matches_client_with_positive_and_negative_sentiment(world):
    client_id = world["client_id"]
    client = world["accounts"].get_client(client_id)
    world["accounts"]._clients[client_id] = client.model_copy(
        update={
            "context": client.context.model_copy(
                update={"favorite_team": "Corinthians"}
            )
        }
    )

    async def fetch_news():
        return [
            NewsItem(
                source="Esportes",
                title="Corinthians conquista vitória no clássico",
                url="https://example.com/esportes/corinthians-vitoria",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.POSITIVE,
            ),
            NewsItem(
                source="Esportes",
                title="Timão sofre derrota fora de casa",
                url="https://example.com/esportes/timao-derrota",
                published_at=datetime(2026, 10, 22),
                sentiment=Sentiment.NEGATIVE,
            ),
        ]

    world["market"].fetch_news = fetch_news
    dashboard = _dashboard(world, FakeLLM())

    impacts = dashboard.news_impact_list(ADVISOR)
    priorities = dashboard.daily_priority_list(ADVISOR)

    assert len(impacts) == 2
    assert [item.interested_clients[0].matched_interest for item in impacts] == [
        "Corinthians",
        "Corinthians",
    ]
    assert [item.interested_clients[0].sentiment for item in impacts] == [
        Sentiment.POSITIVE,
        Sentiment.NEGATIVE,
    ]
    assert all(item.affected_clients == [] for item in impacts)
    assert priorities[0].criticality_score >= 10
    assert priorities[0].next_best_action.title == (
        "Acompanhar notícia ligada a interesse pessoal"
    )


def test_without_api_key_chat_uses_local_fallback(world):
    svc = CopilotChatService(
        OpenAIClient(Settings(openai_api_key="")),
        CopilotTools(
            world["scheduling"],
            world["accounts"],
            world["portfolio"],
            world["market"],
            world["store"],
        ),
        world["accounts"],
        world["store"],
    )
    app.dependency_overrides[get_copilot_service] = lambda: svc
    try:
        res = TestClient(app).post(
            "/api/v1/copilot/chat",
            json={"client_id": world["client_id"], "message": "oi"},
        )
        assert res.status_code == 200
        assert "modo local" in res.json()["reply"]
        assert (
            TestClient(app)
            .get(f"/api/v1/copilot/chat/{world['client_id']}/history")
            .json()
            != []
        )
    finally:
        app.dependency_overrides.clear()


def test_local_fallback_collects_context_and_schedules_with_advisor_summary(world):
    svc = CopilotChatService(
        OpenAIClient(Settings(openai_api_key="")),
        CopilotTools(
            world["scheduling"],
            world["accounts"],
            world["portfolio"],
            world["market"],
            world["store"],
        ),
        world["accounts"],
        world["store"],
    )

    first = _say(svc, world, "Quero agendar uma reunião")
    assert "assunto principal" in first.reply
    for answer in ANSWERS.values():
        result = _say(svc, world, answer)

    assert [tool.name for tool in result.tool_calls] == ["schedule_meeting"]
    assert "resumo do assunto foi encaminhado" in result.reply
    assert "retornará a você" in result.reply
    (meeting,) = world["scheduling"].list_for_client(world["client_id"])
    assert meeting.context is not None
    assert ANSWERS["motivo"] in meeting.context.summary


def _dashboard(world, llm: FakeLLM) -> AdvisorDashboardService:
    return AdvisorDashboardService(
        world["accounts"],
        world["portfolio"],
        DailyAdvisorEngine(),
        world["scheduling"],
        world["market"],
        llm,
    )


def _book_with_context(world):
    llm = FakeLLM(
        *_save_all(), _call("schedule_meeting", topic="CDB que vence"), _text("ok")
    )
    _say(_chat(world, llm), world, "marque")
    return world["scheduling"].list_for_client(world["client_id"])[0]


def test_briefing_combines_context_portfolio_and_news(world):
    _points_cache.clear()
    meeting = _book_with_context(world)
    llm = FakeLLM(_text("- Falar do CDB que vence\n- ITUB4 caiu hoje\n"))

    briefing = _dashboard(world, llm).build_briefing(ADVISOR, meeting.id)

    assert briefing.client_name == "Camila Prates"
    assert briefing.context is not None
    assert briefing.context.answers[0].answer == ANSWERS["motivo"]
    assert (
        briefing.follow_up
        == "Retornar ao cliente com um resumo do assunto: CDB que vence."
    )
    assert briefing.portfolio.total_net_worth == Decimal("200000")
    assert briefing.portfolio.allocation[0].share_pct == 90.0
    assert [n.related_tickers for n in briefing.news] == [
        ["ITUB4"],
        ["TESOURO-SELIC-2029", "CDB-XP-2026"],
    ]
    assert briefing.talking_points == ["Falar do CDB que vence", "ITUB4 caiu hoje"]
    prompt = llm.received[0][0]["content"]
    assert ANSWERS["prazo"] in prompt and "ITUB4" in prompt


def test_briefing_falls_back_when_the_llm_is_down(world):
    _points_cache.clear()
    meeting = _book_with_context(world)

    briefing = _dashboard(
        world, FakeLLM(ExternalServiceError("fora do ar"))
    ).build_briefing(ADVISOR, meeting.id)

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
            id="c1",
            type="function",
            function=SimpleNamespace(
                name="schedule_meeting", arguments='{"topic": "x"}'
            ),
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=None, tool_calls=[call])
                )
            ]
        )

    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=completion))
    )
    monkeypatch.setattr(openai, "OpenAI", lambda **_: fake)
    client = OpenAIClient(Settings(openai_api_key="sk-test", openai_model="m"))

    message = client.chat([{"role": "user", "content": "oi"}], [])
    assert message.tool_calls == [
        LLMToolCall(id="c1", name="schedule_meeting", arguments={"topic": "x"})
    ]
    assert seen["model"] == "m" and seen["tools"] is openai.NOT_GIVEN

    def boom(**_):
        raise openai.APIConnectionError(
            request=httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
        )

    fake.chat.completions.create = boom
    with pytest.raises(ExternalServiceError):
        client.chat([], [])


def test_save_context_accepts_one_answer_at_a_time_and_rejects_bad_input(world):
    tools = CopilotTools(
        world["scheduling"],
        world["accounts"],
        world["portfolio"],
        world["market"],
        world["store"],
    )
    client_id = world["client_id"]

    first = tools.run(
        client_id, "save_meeting_context", {"motivo": " CDB vencendo ", "prazo": ""}
    )
    assert first == {
        "status": "saved",
        "saved": ["motivo"],
        "missing": ["objetivo", "prazo", "mudancas"],
    }
    assert world["store"].intake(client_id)["motivo"].answer == "CDB vencendo"

    assert (
        tools.run(client_id, "save_meeting_context", {"humor": "bom"})["status"]
        == "error"
    )
    assert tools.run(client_id, "save_meeting_context", {})["status"] == "error"
    assert list(world["store"].intake(client_id)) == ["motivo"]
