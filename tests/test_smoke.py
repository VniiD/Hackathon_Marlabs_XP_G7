from datetime import datetime

from fastapi.testclient import TestClient

from src.main import app
from src.modules.market_intelligence.models import CurrencyRate, NewsItem
from src.modules.market_intelligence.services import MarketIntelligenceService, RSSMarketClient

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_client_and_priorities():
    body = {"name": "Ana", "email": "a@x.com", "advisor_id": 1, "risk_profile": "CONSERVADOR"}
    assert client.post("/api/v1/accounts/clients", json=body).status_code == 201
    r = client.get("/api/v1/advisor/1/priorities")
    assert r.status_code == 200 and len(r.json()) >= 1


def test_accounts_profiles_and_signup_routes():
    response = client.get("/api/v1/accounts/profiles")
    assert response.status_code == 200
    payload = response.json()
    assert any(p["role"] == "ADVISOR" for p in payload)

    signup = client.post("/api/v1/accounts/signup", json={"name": "Bruno", "email": "bruno@x.com"})
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

    monkeypatch.setattr("src.modules.market_intelligence.services.RSSMarketClient.fetch_feed", fake_fetch)

    response = client.get("/api/v1/market/news")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["title"] == "Mercado em alta"
    assert payload[0]["url"] == "https://example.com/news/2"
    assert payload[0]["related_tickers"] == ["ITUB4"]


def test_market_quote_falls_back_when_redis_is_unavailable(monkeypatch):
    class FailingRedis:
        def get(self, _key):
            raise RuntimeError("redis unavailable")

    svc = MarketIntelligenceService(redis=FailingRedis())
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
                value="5.36",
                variation_pct="0.12",
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
