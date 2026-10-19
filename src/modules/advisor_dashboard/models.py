from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from src.modules.portfolio.models import AssetClass


class TriggerType(StrEnum):
    MARKET_DROP = "MARKET_DROP"
    PROFILE_MISMATCH = "PROFILE_MISMATCH"
    BIRTHDAY = "BIRTHDAY"
    FAMILY_DATE = "FAMILY_DATE"
    INACTIVITY = "INACTIVITY"


class ClientSignals(BaseModel):
    """Entradas do motor, já agregadas pelos outros módulos."""

    client_id: int
    portfolio_change_pct: float = 0.0
    risk_profile: str
    relationship_triggers: list[TriggerType] = []
    days_since_last_contact: int = 0


class NextBestAction(BaseModel):
    title: str
    rationale: str


class PrioritizedClient(BaseModel):
    client_id: int
    criticality_score: float = Field(ge=0, le=100)
    next_best_action: NextBestAction


class AssetClassAllocation(BaseModel):
    asset_class: AssetClass
    total_value: Decimal
    share_pct: float


class ConsolidatedHolding(BaseModel):
    ticker: str
    asset_class: AssetClass
    total_value: Decimal
    share_pct: float
    clients_count: int


class ClientSegment(BaseModel):
    risk_profile: str
    clients_count: int
    total_aum: Decimal
    aum_share_pct: float


class AdvisorOverview(BaseModel):
    advisor_id: int
    clients_count: int
    total_aum: Decimal
    external_aum: Decimal
    external_cash: Decimal
    by_asset_class: list[AssetClassAllocation]
    holdings: list[ConsolidatedHolding]
    segments: list[ClientSegment]
