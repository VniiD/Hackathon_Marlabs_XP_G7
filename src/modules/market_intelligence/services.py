import re
import time
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser

import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from fastapi import Depends
from redis import Redis

from src.core.config import Settings, get_settings
from src.core.redis_client import get_redis
from src.modules.market_intelligence.models import (
    CurrencyRate,
    NewsItem,
    Quote,
    Sentiment,
)

QUOTES_CHANNEL = "market:quotes"
NEWS_CACHE_TTL_SECONDS = 60
CURRENCY_CACHE_TTL_SECONDS = 300
MAX_NEWS_ITEMS = 250
ADDITIONAL_NEWS_FEEDS = (
    ("https://ge.globo.com/rss/ge/", "ge.globo"),
    ("https://valor.globo.com/rss/valor/", "Valor Econômico"),
    ("https://www.moneytimes.com.br/feed/", "Money Times"),
)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self.parts)


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

    @staticmethod
    def _sentiment(text: str) -> Sentiment:
        normalized = text.casefold()
        negative = (
            "cai",
            "queda",
            "recua",
            "recuo",
            "perda",
            "pressão",
            "risco",
            "rebaixa",
            "derrota",
            "derrotado",
            "derrotada",
            "derrotou",
            "perde",
            "perdeu",
            "eliminado",
            "eliminada",
            "rebaixado",
            "rebaixada",
        )
        positive = (
            "sobe",
            "alta",
            "avança",
            "ganho",
            "lucro",
            "recorde",
            "melhora",
            "eleva",
            "vence",
            "venceu",
            "vitoria",
            "vitória",
            "campeao",
            "campeão",
            "campea",
            "campeã",
            "conquista",
            "ganha",
        )
        words = re.findall(r"[a-zà-ÿ]+", normalized)
        negative_hits = sum(word in words for word in negative)
        positive_hits = sum(word in words for word in positive)
        if negative_hits > positive_hits:
            return Sentiment.NEGATIVE
        if positive_hits > negative_hits:
            return Sentiment.POSITIVE
        return Sentiment.NEUTRAL

    def _parse_xml(self, xml_content: str) -> list[NewsItem]:
        try:
            root = ET.fromstring(xml_content)
        except (ET.ParseError, DefusedXmlException):
            return []

        items: list[NewsItem] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            raw_date = (
                item.findtext("pubDate")
                or item.findtext("published")
                or item.findtext("dc:date")
            )
            raw_description = item.findtext("description") or ""
            description_parser = _HTMLTextExtractor()
            description_parser.feed(raw_description)
            description = description_parser.text()
            text = f"{title} {description}"
            items.append(
                NewsItem(
                    source=self.source_name,
                    title=title or "Sem título",
                    summary=description[:500],
                    url=link or "https://example.com/untitled",
                    published_at=self._parse_date(raw_date),
                    related_tickers=self._extract_tickers(text),
                    sentiment=self._sentiment(text),
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
        self._additional_rss_clients = [
            RSSMarketClient(url, source_name)
            for url, source_name in ADDITIONAL_NEWS_FEEDS
        ]
        self._news_cache: list[NewsItem] = []
        self._news_cached_at = 0.0
        self._currency_cache: list[CurrencyRate] = []
        self._currency_cached_at = 0.0

    def list_news(self, tickers: list[str] | None = None) -> list[NewsItem]:
        tickers_set = {ticker.upper() for ticker in (tickers or [])}
        items: list[NewsItem] = []
        for item in self._fallback_news:
            if not tickers_set or any(
                ticker.upper() in tickers_set for ticker in item.related_tickers
            ):
                items.append(item)
        return items

    def _fallback_quote(self, ticker: str) -> Quote:
        normalized = ticker.upper()
        price = self._fallback_prices.get(normalized, Decimal("10.00"))
        change_pct = (
            Decimal("0.12") if normalized.startswith("ITUB") else Decimal("0.00")
        )
        return Quote(
            ticker=normalized,
            price=price,
            change_pct=change_pct,
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_news(self, force_refresh: bool = False) -> list[NewsItem]:
        now = time.monotonic()
        if (
            self._news_cache
            and not force_refresh
            and now - self._news_cached_at < NEWS_CACHE_TTL_SECONDS
        ):
            return list(self._news_cache)

        clients = [self._rss_client, *self._additional_rss_clients]
        feeds = await asyncio.gather(
            *(client.fetch_feed() for client in clients), return_exceptions=True
        )
        items: list[NewsItem] = []
        seen: set[str] = set()
        for client, feed in zip(clients, feeds):
            if isinstance(feed, BaseException):
                continue
            for item in feed:
                canonical_url = item.url.split("?", 1)[0].rstrip("/").casefold()
                key = canonical_url or item.title.casefold()
                if key in seen:
                    continue
                seen.add(key)
                if client is self._rss_client:
                    items.append(item)
                else:
                    items.append(item.model_copy(update={"source": client.source_name}))
        items.sort(key=lambda item: item.published_at.timestamp(), reverse=True)
        items = items[:MAX_NEWS_ITEMS]
        if items:
            self._news_cache = items
            self._news_cached_at = now
        elif not self._news_cache:
            self._news_cache = self.list_news()
            self._news_cached_at = now
        return list(self._news_cache)

    async def fetch_currency_line(
        self, force_refresh: bool = False
    ) -> list[CurrencyRate]:
        now = time.monotonic()
        if (
            self._currency_cache
            and not force_refresh
            and now - self._currency_cached_at < CURRENCY_CACHE_TTL_SECONDS
        ):
            return list(self._currency_cache)
        self._currency_cache = await self._fetch_currency_line()
        self._currency_cached_at = now
        return list(self._currency_cache)

    async def _fetch_currency_line(self) -> list[CurrencyRate]:
        symbols = "BRL,EUR,GBP,JPY,CHF,CAD,ARS"
        today = date.today()
        previous_day = today - timedelta(days=1)
        api_url = (
            f"https://api.frankfurter.app/{previous_day:%Y-%m-%d}..{today:%Y-%m-%d}"
            f"?from=USD&to={symbols}"
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
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
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
                    variation = (
                        0.0
                        if previous == 0
                        else ((current - previous) / previous) * 100
                    )
                    rows.append(
                        CurrencyRate(
                            code=code,
                            name=labels.get(code, code),
                            value=Decimal(str(current)),
                            variation_pct=Decimal(str(round(variation, 2))),
                            updated_at=datetime.fromisoformat(dates[-1]).replace(
                                tzinfo=timezone.utc
                            ),
                        )
                    )
                return rows
        except Exception:
            fallback = [
                CurrencyRate(
                    code="BRL",
                    name="Real brasileiro",
                    value=Decimal("5.31"),
                    variation_pct=Decimal("0.12"),
                    updated_at=datetime.now(timezone.utc),
                ),
                CurrencyRate(
                    code="EUR",
                    name="Euro",
                    value=Decimal("0.92"),
                    variation_pct=Decimal("0.10"),
                    updated_at=datetime.now(timezone.utc),
                ),
                CurrencyRate(
                    code="GBP",
                    name="Libra esterlina",
                    value=Decimal("0.78"),
                    variation_pct=Decimal("-0.08"),
                    updated_at=datetime.now(timezone.utc),
                ),
                CurrencyRate(
                    code="JPY",
                    name="Iene japonês",
                    value=Decimal("149.20"),
                    variation_pct=Decimal("0.05"),
                    updated_at=datetime.now(timezone.utc),
                ),
                CurrencyRate(
                    code="CHF",
                    name="Franco suíço",
                    value=Decimal("0.90"),
                    variation_pct=Decimal("0.04"),
                    updated_at=datetime.now(timezone.utc),
                ),
                CurrencyRate(
                    code="CAD",
                    name="Dólar canadense",
                    value=Decimal("1.36"),
                    variation_pct=Decimal("0.03"),
                    updated_at=datetime.now(timezone.utc),
                ),
                CurrencyRate(
                    code="ARS",
                    name="Peso argentino",
                    value=Decimal("1025.40"),
                    variation_pct=Decimal("0.02"),
                    updated_at=datetime.now(timezone.utc),
                ),
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

    def analyze_news_impact(
        self, news: NewsItem, client_tickers: list[str]
    ) -> list[str]:
        """Retorna os tickers do cliente afetados pela notícia (stub)."""
        return [t for t in news.related_tickers if t in client_tickers]


_market_service: MarketIntelligenceService | None = None


def get_market_service(
    settings: Settings = Depends(get_settings),
) -> MarketIntelligenceService:
    global _market_service
    if _market_service is None:
        _market_service = MarketIntelligenceService(get_redis(), settings)
    return _market_service
