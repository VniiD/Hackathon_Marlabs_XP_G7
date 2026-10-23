from collections import defaultdict
from decimal import Decimal

from src.modules.accounts.models import ClientProfile, RiskProfile
from src.modules.advisor_dashboard.models import (
    AdvisorOverview,
    AssetClassAllocation,
    ClientSegment,
    ConsolidatedHolding,
)
from src.modules.portfolio.models import AssetClass, UnifiedPortfolio

ZERO = Decimal(0)


def _pct(part: Decimal, total: Decimal) -> float:
    return round(float(part / total * 100), 2) if total else 0.0


def build_overview(
    advisor_id: int,
    clients: list[ClientProfile],
    portfolios: dict[int, UnifiedPortfolio],
) -> AdvisorOverview:
    """Consolida as carteiras de todos os clientes do assessor em uma visão única."""
    by_class: dict[AssetClass, Decimal] = defaultdict(lambda: ZERO)
    by_ticker: dict[str, Decimal] = defaultdict(lambda: ZERO)
    ticker_class: dict[str, AssetClass] = {}
    ticker_clients: dict[str, set[int]] = defaultdict(set)
    segment_aum: dict[RiskProfile, Decimal] = {p: ZERO for p in RiskProfile}
    segment_count: dict[RiskProfile, int] = {p: 0 for p in RiskProfile}
    total = external_aum = external_cash = ZERO

    for client in clients:
        portfolio = portfolios[client.user.id]
        external_holdings = [h for a in portfolio.external_accounts for h in a.holdings]
        cash = sum((a.balance for a in portfolio.external_accounts), ZERO)

        for h in [*portfolio.internal_holdings, *external_holdings]:
            by_class[h.asset_class] += h.market_value
            by_ticker[h.ticker] += h.market_value
            ticker_class[h.ticker] = h.asset_class
            ticker_clients[h.ticker].add(client.user.id)

        external_cash += cash
        external_aum += cash + sum((h.market_value for h in external_holdings), ZERO)
        total += portfolio.total_net_worth
        segment_aum[client.risk_profile] += portfolio.total_net_worth
        segment_count[client.risk_profile] += 1

    return AdvisorOverview(
        advisor_id=advisor_id,
        clients_count=len(clients),
        total_aum=total,
        external_aum=external_aum,
        external_cash=external_cash,
        by_asset_class=sorted(
            (
                AssetClassAllocation(
                    asset_class=c, total_value=v, share_pct=_pct(v, total)
                )
                for c, v in by_class.items()
            ),
            key=lambda a: a.total_value,
            reverse=True,
        ),
        holdings=sorted(
            (
                ConsolidatedHolding(
                    ticker=t,
                    asset_class=ticker_class[t],
                    total_value=v,
                    share_pct=_pct(v, total),
                    clients_count=len(ticker_clients[t]),
                )
                for t, v in by_ticker.items()
            ),
            key=lambda h: h.total_value,
            reverse=True,
        ),
        segments=[
            ClientSegment(
                risk_profile=p,
                clients_count=segment_count[p],
                total_aum=segment_aum[p],
                aum_share_pct=_pct(segment_aum[p], total),
            )
            for p in RiskProfile
        ],
    )
