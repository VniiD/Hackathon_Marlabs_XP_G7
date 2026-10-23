import asyncio
from datetime import datetime
from decimal import Decimal
from typing import cast

import pytest
from redis import Redis
from fastapi.testclient import TestClient

from src.main import app
from src.modules.accounts.models import (
    ClientCreate,
    ClientProfile,
    LoginProfile,
    PersonalContext,
    RiskProfile,
    User,
    UserRole,
)
from src.modules.accounts.services import get_accounts_service
from src.modules.market_intelligence.models import CurrencyRate, NewsItem
from src.modules.market_intelligence.services import (
    MarketIntelligenceService,
    RSSMarketClient,
    get_market_service,
)

client = TestClient(app)


class MemoryAccounts:
    def __init__(self):
        self.clients: dict[int, ClientProfile] = {}
        self.create_client(
            ClientCreate(
                name="Cliente de teste",
                email="cliente-teste@x.com",
                advisor_id=1,
                risk_profile=RiskProfile.MODERADO,
            )
        )

    def create_client(self, data: ClientCreate) -> ClientProfile:
        client_id = max([1, *self.clients]) + 1
        client = ClientProfile(
            user=User(
                id=client_id, name=data.name, email=data.email, role=UserRole.CLIENT
            ),
            advisor_id=data.advisor_id,
            risk_profile=data.risk_profile,
            context=data.context or PersonalContext(),
        )
        self.clients[client_id] = client
        return client

    def sign_up(self, name: str, email: str) -> LoginProfile:
        client = self.create_client(
            ClientCreate(
                name=name,
                email=email,
                advisor_id=1,
                risk_profile=RiskProfile.MODERADO,
            )
        )
        return LoginProfile(
            id=client.user.id,
            name=name,
            email=email,
            role=UserRole.CLIENT,
            needs_onboarding=True,
        )

    def list_profiles(self) -> list[LoginProfile]:
        return [
            LoginProfile(
                id=1,
                name="Assessora de teste",
                email="assessora@x.com",
                role=UserRole.ADVISOR,
            ),
            *[
                LoginProfile(
                    id=client.user.id,
                    name=client.user.name,
                    email=client.user.email,
                    role=UserRole.CLIENT,
                )
                for client in self.clients.values()
            ],
        ]

    def list_clients_by_advisor(self, advisor_id: int) -> list[ClientProfile]:
        return [c for c in self.clients.values() if c.advisor_id == advisor_id]


@pytest.fixture(autouse=True)
def isolate_account_routes():
    app.dependency_overrides[get_accounts_service] = MemoryAccounts
    yield
    app.dependency_overrides.pop(get_accounts_service, None)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_client_and_priorities():
    body = {
        "name": "Ana",
        "email": "a@x.com",
        "advisor_id": 1,
        "risk_profile": "CONSERVADOR",
    }
    assert client.post("/api/v1/accounts/clients", json=body).status_code == 201
    r = client.get("/api/v1/advisor/1/priorities")
    assert r.status_code == 200 and len(r.json()) >= 1


def test_accounts_profiles_and_signup_routes():
    response = client.get("/api/v1/accounts/profiles")
    assert response.status_code == 200
    payload = response.json()
    assert any(p["role"] == "ADVISOR" for p in payload)

    signup = client.post(
        "/api/v1/accounts/signup", json={"name": "Bruno", "email": "bruno@x.com"}
    )
    assert signup.status_code == 200
    body = signup.json()
    assert body["role"] == "CLIENT"
    assert body["needs_onboarding"] is True


def test_rss_market_client_parses_valid_feed():
    xml = """
    <rss version="2.0">
      <channel>
        <title>InfoMoney</title>
        <item>
          <title>Ibovespa reage com PETR4 em alta</title>
          <link>https://example.com/news/1</link>
          <pubDate>Mon, 07 Oct 2024 12:00:00 -0300</pubDate>
        </item>
      </channel>
    </rss>
    """

    items = RSSMarketClient("https://example.com/feed")._parse_xml(xml)
    assert len(items) == 1
    assert items[0].title == "Ibovespa reage com PETR4 em alta"
    assert items[0].url == "https://example.com/news/1"
    assert items[0].related_tickers == ["PETR4"]
    assert isinstance(items[0].published_at, datetime)


def test_rss_parser_rejects_entity_expansion():
    xml = """<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <rss><channel><item><title>&xxe;</title></item></channel></rss>"""

    assert RSSMarketClient("https://example.com/feed")._parse_xml(xml) == []


def test_rss_parser_extracts_interest_and_asset_from_html_description():
    xml = """<rss><channel><item>
            <title>Clássico paulista hoje</title>
            <description><![CDATA[<p>Corinthians conquista vitória; ITUB4 sobe no pregão.</p>]]></description>
        </item></channel></rss>"""

    (item,) = RSSMarketClient("https://example.com/feed")._parse_xml(xml)

    assert "Corinthians" in item.summary
    assert item.related_tickers == ["ITUB4"]
    assert item.sentiment.value == "POSITIVE"


def test_sentiment_does_not_match_negative_word_inside_caixa():
    from src.modules.market_intelligence.models import Sentiment

    assert RSSMarketClient._sentiment("Caixa anuncia resultado") == Sentiment.NEUTRAL


def test_sentiment_recognizes_positive_and_negative_sports_results():
    from src.modules.market_intelligence.models import Sentiment

    assert (
        RSSMarketClient._sentiment("Corinthians conquista vitória no clássico")
        == Sentiment.POSITIVE
    )
    assert (
        RSSMarketClient._sentiment("Timão sofre derrota fora de casa")
        == Sentiment.NEGATIVE
    )


def test_market_news_endpoint_returns_news(monkeypatch):
    async def fake_fetch(self):
        return [
            NewsItem(
                source="InfoMoney",
                title="Mercado em alta",
                url="https://example.com/news/2",
                published_at=datetime(2024, 10, 7, 12, 0, 0),
                related_tickers=["ITUB4"],
            )
        ]

    monkeypatch.setattr(
        "src.modules.market_intelligence.services.RSSMarketClient.fetch_feed",
        fake_fetch,
    )
    service = MarketIntelligenceService(redis=Redis())
    app.dependency_overrides[get_market_service] = lambda: service
    try:
        response = client.get("/api/v1/market/news")
        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["title"] == "Mercado em alta"
        assert payload[0]["url"] == "https://example.com/news/2"
        assert payload[0]["related_tickers"] == ["ITUB4"]
    finally:
        app.dependency_overrides.pop(get_market_service, None)


def test_market_news_cache_refreshes_on_demand(monkeypatch):
    service = MarketIntelligenceService(redis=Redis())
    calls = 0
    version = 1
    rss_clients = [service._rss_client, *service._additional_rss_clients]

    async def fake_fetch():
        nonlocal calls
        calls += 1
        return [
            NewsItem(
                source="Teste",
                title=f"Notícia {version}",
                url="https://example.com/news/1",
                published_at=datetime(2026, 10, 22),
            )
        ]

    for rss_client in rss_clients:
        monkeypatch.setattr(rss_client, "fetch_feed", fake_fetch)
    assert asyncio.run(service.fetch_news())[0].title == "Notícia 1"
    assert asyncio.run(service.fetch_news())[0].title == "Notícia 1"
    version = 2
    assert asyncio.run(service.fetch_news(force_refresh=True))[0].title == "Notícia 2"
    assert calls == len(rss_clients) * 2


def test_market_service_merges_all_configured_news_feeds(monkeypatch):
    service = MarketIntelligenceService(redis=Redis())

    async def fake_fetch(client):
        return [
            NewsItem(
                source=client.source_name,
                title=f"Matéria {client.source_name}",
                url=f"https://example.com/{client.source_name.replace(' ', '-')}/1",
                published_at=datetime(2026, 10, 22),
            )
        ]

    async def fetch_for_client(self):
        return await fake_fetch(self)

    monkeypatch.setattr(RSSMarketClient, "fetch_feed", fetch_for_client)
    items = asyncio.run(service.fetch_news(force_refresh=True))

    assert len(items) == 4
    assert {item.source for item in items} == {
        "InfoMoney",
        "ge.globo",
        "Valor Econômico",
        "Money Times",
    }


def test_currency_cache_refreshes_on_demand(monkeypatch):
    service = MarketIntelligenceService(redis=Redis())
    calls = 0

    async def fake_fetch(self):
        nonlocal calls
        calls += 1
        return [
            CurrencyRate(
                code="BRL",
                name="Real brasileiro",
                value=Decimal("5.00") + calls,
                variation_pct=Decimal("0.1"),
                updated_at=datetime(2026, 10, 22),
            )
        ]

    monkeypatch.setattr(MarketIntelligenceService, "_fetch_currency_line", fake_fetch)
    assert asyncio.run(service.fetch_currency_line())[0].value == Decimal("6.00")
    assert asyncio.run(service.fetch_currency_line())[0].value == Decimal("6.00")
    assert asyncio.run(service.fetch_currency_line(force_refresh=True))[
        0
    ].value == Decimal("7.00")
    assert calls == 2


def test_market_quote_falls_back_when_redis_is_unavailable(monkeypatch):
    class FailingRedis:
        def get(self, _key):
            raise RuntimeError("redis unavailable")

    svc = MarketIntelligenceService(redis=cast(Redis, FailingRedis()))
    quote = svc.get_quote("ITUB4")

    assert quote is not None
    assert quote.ticker == "ITUB4"
    assert quote.price > 0


def test_market_currency_line_endpoint_returns_rates(monkeypatch):
    async def fake_fetch_currency_line(self):
        return [
            CurrencyRate(
                code="USD",
                name="Dólar americano",
                value=Decimal("5.36"),
                variation_pct=Decimal("0.12"),
                updated_at=datetime(2024, 10, 7, 12, 0, 0),
            )
        ]

    monkeypatch.setattr(
        "src.modules.market_intelligence.services.MarketIntelligenceService.fetch_currency_line",
        fake_fetch_currency_line,
    )

    response = client.get("/api/v1/market/currency-line")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["code"] == "USD"
    assert payload[0]["variation_pct"] == "0.12"


def test_advisor_dashboard_routes_are_available():
    overview = client.get("/api/v1/advisor/1/overview")
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["advisor_id"] == 1
    assert payload["clients_count"] >= 1

    meetings = client.get("/api/v1/scheduling/advisors/1/meetings")
    assert meetings.status_code == 200
    assert isinstance(meetings.json(), list)
