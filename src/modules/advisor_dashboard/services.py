import asyncio
from datetime import datetime
from decimal import Decimal

from fastapi import Depends
from pydantic import BaseModel

from src.core.exceptions import ForbiddenError, NotFoundError
from src.modules.accounts.services import AccountsService, get_accounts_service
from src.modules.advisor_dashboard.engine import DailyAdvisorEngine
from src.modules.advisor_dashboard.models import AdvisorOverview, ClientSignals, PrioritizedClient
from src.modules.advisor_dashboard.overview import build_overview
from src.modules.market_intelligence.models import NewsItem, Sentiment
from src.modules.market_intelligence.services import MarketIntelligenceService, get_market_service
from src.modules.portfolio.models import AssetClass, UnifiedPortfolio
from src.modules.portfolio.services import PortfolioService, get_portfolio_service
from src.modules.scheduling.models import MeetingContext
from src.modules.scheduling.services import SchedulingService, get_scheduling_service

_points_cache: dict[int, list[str]] = {}


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
        llm: object | None = None,
    ) -> None:
        self._accounts = accounts
        self._portfolio = portfolio
        self._engine = engine or DailyAdvisorEngine()
        self._scheduling = scheduling
        self._market = market
        self._llm = llm

    def daily_priority_list(self, advisor_id: int) -> list[PrioritizedClient]:
        clients = self._accounts.list_clients_by_advisor(advisor_id)
        signals = [
            ClientSignals(
                client_id=c.user.id,
                risk_profile=c.risk_profile.value if hasattr(c.risk_profile, "value") else str(c.risk_profile),
            )
            for c in clients
        ]
        return self._engine.prioritize(signals)

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
            key_points = self._suggest_talking_points(client.user.name, meeting, portfolio, news)
            _points_cache[meeting_id] = key_points

        return MeetingBriefing(
            client_name=client.user.name,
            meeting=meeting,
            context=meeting.context,
            portfolio=portfolio_summary,
            news=news,
            talking_points=key_points,
        )

    def _portfolio_summary(self, portfolio: UnifiedPortfolio) -> PortfolioSummary:
        totals: dict[AssetClass, Decimal] = {}
        for holding in portfolio.internal_holdings:
            totals[holding.asset_class] = totals.get(holding.asset_class, Decimal("0")) + holding.market_value

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
                    item for item in items if item.related_tickers and (set(item.related_tickers) & tickers or not tickers)
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
                working.append(f"Notícia para comentar sobre {', '.join(item.related_tickers)}.")

        if self._llm is None:
            return [line.strip().rstrip(".") for line in working if line.strip()]

        context_summary = meeting.context.summary if getattr(meeting, "context", None) and meeting.context else ""
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
                line.strip().lstrip("-*• ")
                for line in raw.splitlines()
                if line.strip()
            ]
            cleaned = [line for line in bullet_points if line and line.lower() != "-"]
            if cleaned:
                return cleaned[:2]
        except Exception:
            pass

        fallback = []
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
) -> AdvisorDashboardService:
    return AdvisorDashboardService(accounts, portfolio, DailyAdvisorEngine(), scheduling, market)
