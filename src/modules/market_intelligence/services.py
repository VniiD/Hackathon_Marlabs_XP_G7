import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
from fastapi import Depends
from redis import Redis

from src.core.config import Settings, get_settings
from src.core.redis_client import get_redis
from src.modules.market_intelligence.models import CurrencyRate, NewsItem, Quote, Sentiment

QUOTES_CHANNEL = "market:quotes"


class RSSMarketClient:
    def __init__(self, feed_url: str, source_name: str = "InfoMoney") -> None:
        self.feed_url = feed_url
        self.source_name = source_name

    @staticmethod
    def _parse_date(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(value)
            if dt is not None and dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            if dt is not None:
                return dt.replace(tzinfo=None)
        except (TypeError, ValueError, IndexError):
            pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _extract_tickers(text: str) -> list[str]:
        matches = re.findall(r"\b[A-Z]{2,5}\d{1,2}\b", text)
        seen: set[str] = set()
        ordered: list[str] = []
        for match in matches:
            if match not in seen:
                seen.add(match)
                ordered.append(match)
        return ordered

    def _parse_xml(self, xml_content: str) -> list[NewsItem]:
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []

        items: list[NewsItem] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            raw_date = item.findtext("pubDate") or item.findtext("published") or item.findtext("dc:date")
            description = item.findtext("description") or ""
            text = f"{title} {description}"
            items.append(
                NewsItem(
                    source=self.source_name,
                    title=title or "Sem título",
                    url=link or "https://example.com/untitled",
                    published_at=self._parse_date(raw_date),
                    related_tickers=self._extract_tickers(text),
                    sentiment=Sentiment.NEUTRAL,
                )
            )
        return items

    async def fetch_feed(self) -> list[NewsItem]:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(self.feed_url)
            response.raise_for_status()
            return self._parse_xml(response.text)


class MarketIntelligenceService:
    _fallback_prices: dict[str, Decimal] = {
        "ITUB4": Decimal("33.40"),
        "PETR4": Decimal("31.80"),
        "VALE3": Decimal("72.10"),
        "B3SA3": Decimal("13.50"),
        "KNRI11": Decimal("11.85"),
        "SMLL11": Decimal("9.40"),
    }

    _fallback_news: list[NewsItem] = [
        NewsItem(
            source="InfoMoney",
            title="ITUB4 segue em foco entre analistas",
            summary="Banco cresce com melhora em spreads e liquidez.",
            url="https://example.com/news/2",
            published_at=datetime.now(timezone.utc),
            related_tickers=["ITUB4"],
            sentiment=Sentiment.NEUTRAL,
        ),
        NewsItem(
            source="InfoMoney",
            title="Tesouro Selic segue em atenção para carteira fixa",
            summary="Títulos com vencimento em curto prazo continuam em alta.",
            url="https://example.com/news/3",
            published_at=datetime.now(timezone.utc),
            related_tickers=["TESOURO-SELIC-2029", "CDB-XP-2026"],
            sentiment=Sentiment.NEUTRAL,
        ),
    ]

    def __init__(self, redis: Redis, settings: Settings | None = None) -> None:
        self._redis = redis
        self._settings = settings or Settings()
        self._rss_client = RSSMarketClient(self._settings.market_news_feed_url)

    def list_news(self, tickers: list[str] | None = None) -> list[NewsItem]:
        tickers_set = {ticker.upper() for ticker in (tickers or [])}
        items: list[NewsItem] = []
        for item in self._fallback_news:
            if not tickers_set or any(ticker.upper() in tickers_set for ticker in item.related_tickers):
                items.append(item)
        return items

    def _fallback_quote(self, ticker: str) -> Quote:
        normalized = ticker.upper()
        price = self._fallback_prices.get(normalized, Decimal("10.00"))
        change_pct = Decimal("0.12") if normalized.startswith("ITUB") else Decimal("0.00")
        return Quote(
            ticker=normalized,
            price=price,
            change_pct=change_pct,
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_news(self) -> list[NewsItem]:
        return await self._rss_client.fetch_feed()

    async def fetch_currency_line(self) -> list[CurrencyRate]:
        symbols = "BRL,EUR,GBP,JPY,CHF,CAD,ARS"
        today = date.today()
        previous_day = today - timedelta(days=1)
        api_url = (
            "https://api.exchangerate.host/timeseries"
            f"?start_date={previous_day:%Y-%m-%d}&end_date={today:%Y-%m-%d}&base=USD&symbols={symbols}"
        )
        labels = {
            "BRL": "Real brasileiro",
            "EUR": "Euro",
            "GBP": "Libra esterlina",
            "JPY": "Iene japonês",
            "CHF": "Franco suíço",
            "CAD": "Dólar canadense",
            "ARS": "Peso argentino",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                payload = response.json()
                rates = payload.get("rates", {})
                if not rates:
                    raise ValueError("Sem taxa de câmbio disponível")

                dates = sorted(rates)
                previous_rates = rates[dates[0]]
                latest_rates = rates[dates[-1]]
                rows: list[CurrencyRate] = []

                for code in ["BRL", "EUR", "GBP", "JPY", "CHF", "CAD", "ARS"]:
                    if code not in latest_rates:
                        continue
                    current = float(latest_rates[code])
                    previous = float(previous_rates.get(code, current))
                    variation = 0.0 if previous == 0 else ((current - previous) / previous) * 100
                    rows.append(
                        CurrencyRate(
                            code=code,
                            name=labels.get(code, code),
                            value=Decimal(str(current)),
                            variation_pct=Decimal(str(round(variation, 2))),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                return rows
        except Exception:
            fallback = [
                CurrencyRate(code="BRL", name="Real brasileiro", value=Decimal("5.31"), variation_pct=Decimal("0.12"), updated_at=datetime.now(timezone.utc)),
                CurrencyRate(code="EUR", name="Euro", value=Decimal("0.92"), variation_pct=Decimal("0.10"), updated_at=datetime.now(timezone.utc)),
                CurrencyRate(code="GBP", name="Libra esterlina", value=Decimal("0.78"), variation_pct=Decimal("-0.08"), updated_at=datetime.now(timezone.utc)),
                CurrencyRate(code="JPY", name="Iene japonês", value=Decimal("149.20"), variation_pct=Decimal("0.05"), updated_at=datetime.now(timezone.utc)),
                CurrencyRate(code="CHF", name="Franco suíço", value=Decimal("0.90"), variation_pct=Decimal("0.04"), updated_at=datetime.now(timezone.utc)),
                CurrencyRate(code="CAD", name="Dólar canadense", value=Decimal("1.36"), variation_pct=Decimal("0.03"), updated_at=datetime.now(timezone.utc)),
                CurrencyRate(code="ARS", name="Peso argentino", value=Decimal("1025.40"), variation_pct=Decimal("0.02"), updated_at=datetime.now(timezone.utc)),
            ]
            return fallback

    def publish_quote(self, quote: Quote) -> None:
        try:
            self._redis.set(f"quote:{quote.ticker}", quote.model_dump_json())
            self._redis.publish(QUOTES_CHANNEL, quote.model_dump_json())
        except Exception:
            return

    def get_quote(self, ticker: str) -> Quote | None:
        key = f"quote:{ticker.upper()}"
        try:
            raw = self._redis.get(key)
            if raw:
                return Quote.model_validate_json(raw)
        except Exception:
            pass
        return self._fallback_quote(ticker)

    def analyze_news_impact(self, news: NewsItem, client_tickers: list[str]) -> list[str]:
        """Retorna os tickers do cliente afetados pela notícia (stub)."""
        return [t for t in news.related_tickers if t in client_tickers]


def get_market_service(
    settings: Settings = Depends(get_settings),
) -> MarketIntelligenceService:
    return MarketIntelligenceService(get_redis(), settings)
