from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class AssetClass(StrEnum):
    RENDA_FIXA = "RENDA_FIXA"
    ACOES = "ACOES"
    FUNDOS = "FUNDOS"
    CRIPTO = "CRIPTO"
    OUTROS = "OUTROS"


class Holding(BaseModel):
    ticker: str
    asset_class: AssetClass
    quantity: Decimal = Field(ge=0)
    market_value: Decimal = Field(ge=0)
    institution: str = "INTERNAL"


class ExternalAccount(BaseModel):
    institution: str
    account_id: str
    balance: Decimal
    holdings: list[Holding] = []


class UnifiedPortfolio(BaseModel):
    client_id: int
    internal_holdings: list[Holding]
    external_accounts: list[ExternalAccount]
    total_net_worth: Decimal


class ChangeKind(StrEnum):
    APORTE = "APORTE"
    RESGATE = "RESGATE"
    REBALANCEAMENTO = "REBALANCEAMENTO"


class ChangeRequestCreate(BaseModel):
    client_id: int
    kind: ChangeKind
    message: str


class ChangeRequest(ChangeRequestCreate):
    id: int
    created_at: datetime
