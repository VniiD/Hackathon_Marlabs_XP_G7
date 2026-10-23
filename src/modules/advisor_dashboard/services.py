import asyncio
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from fastapi import Depends
from pydantic import BaseModel

from src.core.exceptions import ForbiddenError, NotFoundError
from src.modules.accounts.services import AccountsService, get_accounts_service
from src.modules.advisor_dashboard.engine import DailyAdvisorEngine
from src.modules.advisor_dashboard.models import (
    AdvisorOverview,
    AffectedClient,
    ClientSignals,
    InterestedClient,
    NewsImpact,
    PrioritizedClient,
)
from src.modules.advisor_dashboard.overview import build_overview
from src.modules.copilot_chat.services import get_llm_client
from src.modules.copilot_chat.llm import LLMClient
from src.modules.market_intelligence.models import NewsItem, Sentiment
from src.modules.market_intelligence.services import (
    MarketIntelligenceService,
    get_market_service,
)
from src.modules.portfolio.models import AssetClass, UnifiedPortfolio
from src.modules.portfolio.services import PortfolioService, get_portfolio_service
from src.modules.scheduling.models import MeetingContext
from src.modules.scheduling.services import SchedulingService, get_scheduling_service

_points_cache: dict[int, list[str]] = {}

_TEAM_ALIASES = {
    "corinthians": ("corinthians", "timao", "sccp"),
    "palmeiras": ("palmeiras", "verdao", "alviverde paulista"),
    "flamengo": ("flamengo", "mengao", "rubro-negro carioca"),
    "gremio": ("gremio", "imortal tricolor"),
    "internacional": ("internacional", "inter", "colorado gaucho"),
    "sao paulo": ("sao paulo", "spfc", "tricolor paulista"),
    "santos": ("santos", "peixe"),
    "vasco": ("vasco", "vasco da gama", "cruz-maltino"),
    "botafogo": ("botafogo", "fogao"),
    "fluminense": ("fluminense", "flu", "tricolor carioca"),
}


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalize_text(text)
    normalized_phrase = _normalize_text(phrase).strip()
    return bool(
        normalized_phrase
        and re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
            normalized_text,
        )
    )


def _team_terms(team: str) -> tuple[str, ...]:
    normalized = _normalize_text(team).strip()
    return _TEAM_ALIASES.get(normalized, (team,))


def _is_sports_news(item: NewsItem) -> bool:
    source = item.source.casefold()
    path = item.url.casefold().split("?", 1)[0]
    return "ge.globo" in source or any(
        marker in path for marker in ("/futebol/", "/esportes/", "/corrida-e-duathlon/")
    )


def _is_relevant_hobby_match(interest: str, item: NewsItem) -> bool:
    hobby = _normalize_text(interest).strip()
    if hobby in {"corrida", "ciclismo", "golfe", "pesca"}:
        return _is_sports_news(item)
    if _contains_phrase(item.title, interest):
        return True
    return _is_sports_news(item) and _contains_phrase(item.summary, interest)


def _is_financial_news(item: NewsItem) -> bool:
    path = item.url.casefold().split("?", 1)[0]
    source = _normalize_text(item.source)
    if any(
        section in path
        for section in ("/mercados/", "/onde-investir/", "/minhas-financas/")
    ):
        return True
    if source == "valor economico":
        return any(
            section in path
            for section in ("/financas/", "/empresas/", "/agronegocios/")
        )
    return source == "money times" and "/politica/" not in path


class AssetAllocation(BaseModel):
    asset_class: AssetClass
    value: Decimal
    share_pct: float


class PortfolioSummary(BaseModel):
    total_net_worth: Decimal
    allocation: list[AssetAllocation] = []


class MeetingBriefing(BaseModel):
    client_name: str
    meeting: object
    context: MeetingContext | None = None
    follow_up: str = ""
    portfolio: PortfolioSummary
    news: list[NewsItem]
    talking_points: list[str] = []


class AdvisorDashboardService:
    def __init__(
        self,
        accounts: AccountsService,
        portfolio: PortfolioService | None = None,
        engine: DailyAdvisorEngine | None = None,
        scheduling: SchedulingService | None = None,
        market: MarketIntelligenceService | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self._accounts = accounts
        self._portfolio = portfolio
        self._engine = engine or DailyAdvisorEngine()
        self._scheduling = scheduling
        self._market = market
        self._llm = llm

    def daily_priority_list(self, advisor_id: int) -> list[PrioritizedClient]:
        clients = self._accounts.list_clients_by_advisor(advisor_id)
        portfolios = self._client_portfolios(clients)
        news = self._match_portfolio_tickers(self._load_news(portfolios), portfolios)
        currency_rates = self._load_currency_rates()
        impacts = self._news_impacts(clients, portfolios, news)
        personal_matches = self._personal_news_matches(clients, news)
        signals = []
        for client in clients:
            client_impacts = impacts.get(client.user.id, [])
            negative_impacts = [
                (item, row)
                for item, row in client_impacts
                if item.sentiment == Sentiment.NEGATIVE
            ]
            client_personal_matches = personal_matches.get(client.user.id, [])
            negative_personal = [
                (item, match)
                for item, match in client_personal_matches
                if match.sentiment == Sentiment.NEGATIVE
            ]
            risk = (
                client.risk_profile.value
                if hasattr(client.risk_profile, "value")
                else str(client.risk_profile)
            )
            risk_weight = {"CONSERVADOR": 1.5, "MODERADO": 1.0, "ARROJADO": 0.6}.get(
                risk, 1.0
            )
            impact_score = min(
                40.0,
                sum(row.exposure_pct for _, row in negative_impacts)
                * 1.0
                * risk_weight,
            )
            currency_score, currency_summary = self._currency_impact(
                portfolios[client.user.id], currency_rates, risk_weight
            )
            signals.append(
                ClientSignals(
                    client_id=client.user.id,
                    risk_profile=risk,
                    news_impact_score=impact_score,
                    currency_impact_score=currency_score,
                    personal_news_score=min(20.0, 10.0 * len(negative_personal)),
                    news_summary=(
                        "; ".join(item.title for item, _ in negative_impacts[:2])
                        if negative_impacts
                        else ""
                    ),
                    currency_summary=currency_summary,
                    personal_news_summary=(
                        "; ".join(
                            f"{match.matched_interest} ({match.sentiment.value.lower()}): {item.title}"
                            for item, match in client_personal_matches[:2]
                        )
                    ),
                    personal_news_sentiment=(
                        negative_personal[0][1].sentiment
                        if negative_personal
                        else client_personal_matches[0][1].sentiment
                        if client_personal_matches
                        else None
                    ),
                )
            )
        signals = self._apply_llm_adjustment(signals)
        return self._engine.prioritize(signals)

    def _load_currency_rates(self):
        if self._market is None:
            return []
        try:
            return asyncio.run(self._market.fetch_currency_line())
        except Exception:
            return []

    @staticmethod
    def _currency_impact(
        portfolio: UnifiedPortfolio, rates, risk_weight: float
    ) -> tuple[float, str]:
        total_value = portfolio.total_net_worth
        if total_value <= 0 or not rates:
            return 0.0, ""

        sensitive_value = sum(
            (
                holding.market_value
                for holding in AdvisorDashboardService._holdings(portfolio)
                if holding.asset_class in (AssetClass.ACOES, AssetClass.CRIPTO)
            ),
            Decimal("0"),
        )
        sensitive_share = float(sensitive_value / total_value)
        if sensitive_share <= 0:
            return 0.0, ""

        usd_variation = next(
            (abs(float(rate.variation_pct)) for rate in rates if rate.code == "BRL"),
            0.0,
        )
        score = min(15.0, usd_variation * sensitive_share * risk_weight * 2.0)
        if score <= 0:
            return 0.0, ""
        summary = (
            f"BRL variou {usd_variation:.2f}% e {sensitive_share:.0%} da carteira "
            "está em ações ou cripto (proxy de sensibilidade cambial)."
        )
        return score, summary

    def _apply_llm_adjustment(
        self, signals: list[ClientSignals]
    ) -> list[ClientSignals]:
        if self._llm is None or not signals:
            return signals

        deterministic = {
            signal.client_id: self._engine.score(signal) for signal in signals
        }
        payload = [
            {
                "client_id": signal.client_id,
                "risk_profile": signal.risk_profile,
                "base_score": round(deterministic[signal.client_id], 2),
                "news": signal.news_summary,
                "personal_interest": signal.personal_news_summary,
                "currency": signal.currency_summary,
            }
            for signal in signals
        ]
        prompt = (
            "Avalie somente a urgência de contato humano para os clientes abaixo. "
            "Não recomende ativos, não invente fatos e não altere os scores-base. "
            "Retorne JSON puro como uma lista de objetos com client_id, adjustment "
            "e rationale. adjustment deve ser número entre 0 e 10; use 0 quando "
            "os sinais não justificarem urgência adicional. Dados: "
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = self._llm.chat([{"role": "user", "content": prompt}], [])
            suggestions = json.loads(response.content or "[]")
        except Exception:
            return signals
        if not isinstance(suggestions, list):
            return signals

        allowed = {signal.client_id: signal for signal in signals}
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                continue
            try:
                client_id = int(suggestion["client_id"])
                adjustment = min(10.0, max(0.0, float(suggestion["adjustment"])))
            except (KeyError, TypeError, ValueError):
                continue
            signal = allowed.get(client_id)
            if signal is None:
                continue
            signal.llm_impact_score = adjustment
            rationale = suggestion.get("rationale")
            if isinstance(rationale, str):
                signal.llm_summary = rationale[:240]
        return signals

    def news_impact_list(self, advisor_id: int) -> list[NewsImpact]:
        clients = self._accounts.list_clients_by_advisor(advisor_id)
        portfolios = self._client_portfolios(clients)
        all_news = self._match_portfolio_tickers(
            self._load_news(portfolios), portfolios
        )
        portfolio_tickers = {
            holding.ticker.upper()
            for portfolio in portfolios.values()
            for holding in self._holdings(portfolio)
        }
        personal_matches = self._personal_news_matches(clients, all_news)
        news = []
        for item, item_matches in self._items_with_personal_matches(
            all_news, personal_matches
        ):
            related = portfolio_tickers & {
                ticker.upper() for ticker in item.related_tickers
            }
            in_financial_section = _is_financial_news(item)
            if related or item_matches or in_financial_section:
                news.append(item)
        impacts = self._news_impacts(clients, portfolios, news)
        result = []
        for index, item in enumerate(news, start=1):
            affected = [
                row
                for client in clients
                for impacted_news, row in impacts.get(client.user.id, [])
                if impacted_news.title == item.title
            ]
            interested = [
                match
                for client in clients
                for matched_news, match in personal_matches.get(client.user.id, [])
                if matched_news.title == item.title
            ]
            result.append(
                NewsImpact(
                    id=index,
                    source=item.source,
                    title=item.title,
                    summary=item.summary or item.title,
                    url=item.url,
                    published_at=item.published_at,
                    related_tickers=item.related_tickers,
                    sentiment=item.sentiment,
                    affected_clients=affected,
                    interested_clients=interested,
                )
            )
        return result

    @staticmethod
    def _items_with_personal_matches(news, matches):
        return [
            (
                item,
                [
                    match
                    for client_matches in matches.values()
                    for matched_news, match in client_matches
                    if matched_news.title == item.title
                ],
            )
            for item in news
        ]

    @staticmethod
    def _personal_news_matches(clients, news):
        matches: dict[int, list[tuple[NewsItem, InterestedClient]]] = {
            client.user.id: [] for client in clients
        }
        for client in clients:
            context = client.context
            interests: list[tuple[str, str, tuple[str, ...]]] = []
            if context.favorite_team:
                interests.append(
                    (
                        context.favorite_team,
                        "favorite_team",
                        _team_terms(context.favorite_team),
                    )
                )
            interests.extend(
                (hobby, "hobby", (hobby,))
                for hobby in context.hobbies
                if len(hobby.strip()) >= 4
            )
            for item in news:
                searchable = f"{item.title} {item.summary}"
                for interest, interest_type, terms in interests:
                    if interest_type == "hobby" and not _is_relevant_hobby_match(
                        interest, item
                    ):
                        continue
                    if any(_contains_phrase(searchable, term) for term in terms):
                        matches[client.user.id].append(
                            (
                                item,
                                InterestedClient(
                                    client_id=client.user.id,
                                    client_name=client.user.name,
                                    matched_interest=interest,
                                    interest_type=interest_type,
                                    sentiment=item.sentiment,
                                ),
                            )
                        )
                        break
        return matches

    @classmethod
    def _match_portfolio_tickers(
        cls,
        news: list[NewsItem],
        portfolios: dict[int, UnifiedPortfolio],
    ) -> list[NewsItem]:
        holdings = [
            holding
            for portfolio in portfolios.values()
            for holding in cls._holdings(portfolio)
        ]
        matched_news = []
        for item in news:
            searchable = _normalize_text(f"{item.title} {item.summary}")
            matched = list(item.related_tickers)
            for holding in holdings:
                ticker = holding.ticker
                if _contains_phrase(searchable, ticker) and ticker.upper() not in {
                    value.upper() for value in matched
                }:
                    matched.append(ticker.upper())
            matched_news.append(
                item.model_copy(update={"related_tickers": matched})
                if matched != item.related_tickers
                else item
            )
        return matched_news

    def _client_portfolios(self, clients) -> dict[int, UnifiedPortfolio]:
        portfolio_service = self._portfolio or get_portfolio_service()
        return {
            client.user.id: portfolio_service.get_unified_portfolio(client.user.id)
            for client in clients
        }

    def _load_news(self, portfolios: dict[int, UnifiedPortfolio]) -> list[NewsItem]:
        if self._market is None:
            return []
        try:
            items = asyncio.run(self._market.fetch_news())
            if items:
                return items
        except Exception:
            pass
        tickers = sorted(
            {
                holding.ticker.upper()
                for portfolio in portfolios.values()
                for holding in self._holdings(portfolio)
            }
        )
        list_news = getattr(self._market, "list_news", None)
        return list_news(tickers) if callable(list_news) else []

    @staticmethod
    def _holdings(portfolio: UnifiedPortfolio):
        yield from portfolio.internal_holdings
        for account in portfolio.external_accounts:
            yield from account.holdings

    @classmethod
    def _news_impacts(
        cls,
        clients,
        portfolios: dict[int, UnifiedPortfolio],
        news: list[NewsItem],
    ) -> dict[int, list[tuple[NewsItem, AffectedClient]]]:
        impacts: dict[int, list[tuple[NewsItem, AffectedClient]]] = {
            client.user.id: [] for client in clients
        }
        news_with_tickers = [item for item in news if item.related_tickers]
        for client in clients:
            portfolio = portfolios[client.user.id]
            holdings = list(cls._holdings(portfolio))
            total_value = portfolio.total_net_worth
            for item in news_with_tickers:
                related = {ticker.upper() for ticker in item.related_tickers}
                exposure = sum(
                    (
                        holding.market_value
                        for holding in holdings
                        if holding.ticker.upper() in related
                    ),
                    Decimal("0"),
                )
                if exposure <= 0:
                    continue
                impacts[client.user.id].append(
                    (
                        item,
                        AffectedClient(
                            client_id=client.user.id,
                            client_name=client.user.name,
                            exposure_value=exposure,
                            exposure_pct=float(exposure / total_value * 100)
                            if total_value
                            else 0.0,
                        ),
                    )
                )
        return impacts

    def overview(self, advisor_id: int) -> AdvisorOverview:
        clients = self._accounts.list_clients_by_advisor(advisor_id)
        portfolio_service = self._portfolio or get_portfolio_service()
        portfolios = {
            client.user.id: portfolio_service.get_unified_portfolio(client.user.id)
            for client in clients
        }
        return build_overview(advisor_id, clients, portfolios)

    def change_requests(self, advisor_id: int):
        portfolio_service = self._portfolio or get_portfolio_service()
        return portfolio_service.list_change_requests_for_advisor(advisor_id)

    def build_briefing(self, advisor_id: int, meeting_id: int) -> MeetingBriefing:
        if self._scheduling is None:
            raise NotFoundError("Agenda indisponível")

        meeting = self._scheduling.get(meeting_id)
        if meeting.advisor_id != advisor_id:
            raise ForbiddenError("A reunião não pertence a este assessor")

        client = self._accounts.get_client(meeting.client_id)
        portfolio_service = self._portfolio or get_portfolio_service()
        portfolio = portfolio_service.get_unified_portfolio(meeting.client_id)
        portfolio_summary = self._portfolio_summary(portfolio)
        news = self._relevant_news(portfolio)

        key_points = _points_cache.get(meeting_id)
        if key_points is None:
            key_points = self._suggest_talking_points(
                client.user.name, meeting, portfolio, news
            )
            _points_cache[meeting_id] = key_points

        return MeetingBriefing(
            client_name=client.user.name,
            meeting=meeting,
            context=meeting.context,
            follow_up=(
                f"Retornar ao cliente com um resumo do assunto: {meeting.topic}."
                if meeting.context and meeting.context.summary
                else ""
            ),
            portfolio=portfolio_summary,
            news=news,
            talking_points=key_points,
        )

    def _portfolio_summary(self, portfolio: UnifiedPortfolio) -> PortfolioSummary:
        totals: dict[AssetClass, Decimal] = {}
        for holding in portfolio.internal_holdings:
            totals[holding.asset_class] = (
                totals.get(holding.asset_class, Decimal("0")) + holding.market_value
            )

        total_value = portfolio.total_net_worth
        allocation = [
            AssetAllocation(
                asset_class=asset_class,
                value=value,
                share_pct=(float(value / total_value) * 100) if total_value else 0.0,
            )
            for asset_class, value in totals.items()
        ]

        if not allocation:
            allocation = [
                AssetAllocation(
                    asset_class=AssetClass.OUTROS,
                    value=Decimal("0"),
                    share_pct=0.0,
                )
            ]

        return PortfolioSummary(total_net_worth=total_value, allocation=allocation)

    def _relevant_news(self, portfolio: UnifiedPortfolio) -> list[NewsItem]:
        tickers = {holding.ticker for holding in portfolio.internal_holdings}
        if self._market is not None:
            list_news = getattr(self._market, "list_news", None)
            if callable(list_news):
                items = list_news(sorted(tickers))
                if items:
                    return items[:5]
            try:
                items = asyncio.run(self._market.fetch_news())
            except Exception:
                items = []
            if items:
                filtered = [
                    item
                    for item in items
                    if item.related_tickers
                    and (set(item.related_tickers) & tickers or not tickers)
                ]
                if filtered:
                    return filtered[:5]

        if tickers:
            ordered = sorted(tickers)
            return [
                NewsItem(
                    source="Portfólio",
                    title=f"Revisar exposição em {ordered[0]}",
                    summary=f"Notícia para comentar sobre {ordered[0]}",
                    published_at=datetime.utcnow(),
                    related_tickers=[ordered[0]],
                    sentiment=Sentiment.NEUTRAL,
                ),
                NewsItem(
                    source="Portfólio",
                    title="Monitorar títulos de renda fixa",
                    summary="Notícia para comentar sobre a carteira do cliente",
                    published_at=datetime.utcnow(),
                    related_tickers=["TESOURO-SELIC-2029", "CDB-XP-2026"],
                    sentiment=Sentiment.NEUTRAL,
                ),
            ]

        return [
            NewsItem(
                source="Portfólio",
                title="Notícia para comentar",
                summary="Notícia para comentar sobre a carteira do cliente",
                published_at=datetime.utcnow(),
                related_tickers=["ITUB4"],
                sentiment=Sentiment.NEUTRAL,
            )
        ]

    def _suggest_talking_points(
        self,
        client_name: str,
        meeting,
        portfolio: UnifiedPortfolio,
        news: list[NewsItem],
    ) -> list[str]:
        working = [
            f"Reunião com {client_name} sobre {meeting.topic or 'a carteira'}.",
            f"Patrimônio total: {portfolio.total_net_worth}.",
        ]

        for item in news[:3]:
            if item.related_tickers:
                working.append(
                    f"Notícia para comentar sobre {', '.join(item.related_tickers)}."
                )

        if self._llm is None:
            return [line.strip().rstrip(".") for line in working if line.strip()]

        context_summary = (
            meeting.context.summary
            if getattr(meeting, "context", None) and meeting.context
            else ""
        )
        tickers = sorted({ticker for item in news for ticker in item.related_tickers})
        prompt = (
            "Você é o assessor financeiro. Gere 2 pontos curtos em português para conversar com o cliente "
            f"sobre a reunião de {meeting.topic or 'a carteira'} com o contexto: {context_summary or 'Sem contexto extra'}. "
            f"Inclua os ativos relevantes {', '.join(tickers) if tickers else 'da carteira'}. "
            "Responda em bullets com o prefixo '- '."
        )
        try:
            response = self._llm.chat([{"role": "user", "content": prompt}], [])
            raw = response.content or ""
            bullet_points = [
                line.strip().lstrip("-*• ") for line in raw.splitlines() if line.strip()
            ]
            cleaned = [line for line in bullet_points if line and line.lower() != "-"]
            if cleaned:
                return cleaned[:2]
        except Exception:
            pass

        fallback: list[str] = []
        if meeting.context and meeting.context.answers:
            fallback.extend(a.answer for a in meeting.context.answers[:2])
        fallback.extend(
            f"Notícia para comentar sobre {', '.join(item.related_tickers)}"
            for item in news[:2]
            if item.related_tickers
        )
        if fallback:
            return fallback
        return ["Notícia para comentar sobre a carteira do cliente"]


def get_dashboard_service(
    accounts: AccountsService = Depends(get_accounts_service),
    portfolio: PortfolioService = Depends(get_portfolio_service),
    scheduling: SchedulingService = Depends(get_scheduling_service),
    market: MarketIntelligenceService = Depends(get_market_service),
    llm: LLMClient = Depends(get_llm_client),
) -> AdvisorDashboardService:
    return AdvisorDashboardService(
        accounts, portfolio, DailyAdvisorEngine(), scheduling, market, llm
    )
