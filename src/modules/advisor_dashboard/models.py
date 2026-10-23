from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from src.modules.market_intelligence.models import Sentiment
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
    news_impact_score: float = Field(default=0.0, ge=0, le=100)
    currency_impact_score: float = Field(default=0.0, ge=0, le=100)
    personal_news_score: float = Field(default=0.0, ge=0, le=20)
    llm_impact_score: float = Field(default=0.0, ge=0, le=10)
    news_summary: str = ""
    currency_summary: str = ""
    personal_news_summary: str = ""
    personal_news_sentiment: Sentiment | None = None
    llm_summary: str = ""


class NextBestAction(BaseModel):
    title: str
    rationale: str


class PrioritizedClient(BaseModel):
    client_id: int
    criticality_score: float = Field(ge=0, le=100)
    next_best_action: NextBestAction


class AffectedClient(BaseModel):
    client_id: int
    client_name: str
    exposure_value: Decimal
    exposure_pct: float


class InterestedClient(BaseModel):
    client_id: int
    client_name: str
    matched_interest: str
    interest_type: str
    sentiment: Sentiment


class NewsImpact(BaseModel):
    id: int
    source: str
    title: str
    summary: str
    url: str
    published_at: datetime
    related_tickers: list[str]
    sentiment: Sentiment
    affected_clients: list[AffectedClient]
    interested_clients: list[InterestedClient] = []


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
