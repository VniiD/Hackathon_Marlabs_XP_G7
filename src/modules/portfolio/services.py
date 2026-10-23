from datetime import datetime
from decimal import Decimal

from src.modules.accounts.services import get_accounts_service
from src.modules.portfolio.models import (
    ChangeRequest,
    ChangeRequestCreate,
    Holding,
    UnifiedPortfolio,
)
from src.modules.portfolio.open_finance import (
    OpenFinanceIntegrationService,
    get_open_finance_service,
)


class PortfolioService:
    def __init__(self, open_finance: OpenFinanceIntegrationService) -> None:
        self._open_finance = open_finance
        self._internal_holdings: dict[int, list[Holding]] = {}
        self._change_requests: list[ChangeRequest] = []

    def set_internal_holdings(self, client_id: int, holdings: list[Holding]) -> None:
        self._internal_holdings[client_id] = list(holdings)

    def list_internal_holdings(self, client_id: int) -> list[Holding]:
        return list(self._internal_holdings.get(client_id, []))

    def get_unified_portfolio(self, client_id: int) -> UnifiedPortfolio:
        internal = self.list_internal_holdings(client_id)
        external = self._open_finance.fetch_external_accounts(client_id)
        total = sum((h.market_value for h in internal), Decimal(0)) + sum(
            (a.balance for a in external), Decimal(0)
        )
        return UnifiedPortfolio(
            client_id=client_id,
            internal_holdings=internal,
            external_accounts=external,
            total_net_worth=total,
        )

    def create_change_request(self, req: ChangeRequestCreate) -> ChangeRequest:
        item = ChangeRequest(
            id=len(self._change_requests) + 1,
            client_id=req.client_id,
            kind=req.kind,
            message=req.message,
            created_at=datetime.utcnow(),
        )
        self._change_requests.append(item)
        return item

    def list_change_requests_for_advisor(self, advisor_id: int) -> list[ChangeRequest]:
        client_ids = {
            c.user.id
            for c in get_accounts_service().list_clients_by_advisor(advisor_id)
        }
        return [req for req in self._change_requests if req.client_id in client_ids]


_service: PortfolioService | None = None


def get_portfolio_service() -> PortfolioService:
    global _service
    open_finance = get_open_finance_service()
    if _service is None or _service._open_finance is not open_finance:
        _service = PortfolioService(open_finance)
    return _service
