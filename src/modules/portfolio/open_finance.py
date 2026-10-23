from src.core.config import Settings, get_settings
from src.modules.portfolio.models import ExternalAccount


class OpenFinanceIntegrationService:
    """Unifica contas/patrimônio de outras instituições via Open Finance."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.open_finance_base_url
        self._external_accounts: dict[int, list[ExternalAccount]] = {}

    def link_external_accounts(
        self, client_id: int, accounts: list[ExternalAccount]
    ) -> None:
        self._external_accounts[client_id] = list(accounts)

    def fetch_external_accounts(self, client_id: int) -> list[ExternalAccount]:
        # TODO: consentimento OAuth + chamadas httpx a self._base_url
        return list(self._external_accounts.get(client_id, []))


_service = None


def get_open_finance_service() -> OpenFinanceIntegrationService:
    global _service
    if _service is None:
        _service = OpenFinanceIntegrationService(get_settings())
    return _service
