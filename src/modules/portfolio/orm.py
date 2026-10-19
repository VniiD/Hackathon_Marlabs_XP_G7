"""Tabelas do módulo portfolio (inclui Open Finance). Esquema canônico: db/01_schema.sql."""

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, FetchedValue, ForeignKey, ForeignKeyConstraint, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.modules.portfolio.models import AssetClass, ExternalAccount, Holding

INTERNAL = "INTERNAL"


class OpenFinanceConsentRecord(Base):
    __tablename__ = "open_finance_consents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.user_id", ondelete="CASCADE"))
    institution: Mapped[str] = mapped_column(Text)
    external_consent_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="PENDING")  # PENDING | ACTIVE | REVOKED | EXPIRED
    permissions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list)
    granted_at: Mapped[dt.datetime | None]
    expires_at: Mapped[dt.datetime | None]
    revoked_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    accounts: Mapped[list["ExternalAccountRecord"]] = relationship(
        back_populates="consent", cascade="all, delete-orphan"
    )


class ExternalAccountRecord(Base):
    __tablename__ = "external_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["consent_id", "client_id"],
            ["open_finance_consents.id", "open_finance_consents.client_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    consent_id: Mapped[int] = mapped_column(BigInteger)
    client_id: Mapped[int] = mapped_column(BigInteger)
    institution: Mapped[str] = mapped_column(Text)
    account_id: Mapped[str] = mapped_column(Text)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    synced_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    consent: Mapped[OpenFinanceConsentRecord] = relationship(back_populates="accounts")
    holdings: Mapped[list["HoldingRecord"]] = relationship(
        back_populates="external_account", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_model(self) -> ExternalAccount:
        return ExternalAccount(
            institution=self.institution,
            account_id=self.account_id,
            balance=self.balance,
            holdings=[h.to_model() for h in self.holdings],
        )


class HoldingRecord(Base):
    """external_account_id NULL = custódia XP ("INTERNAL"); senão, posição via Open Finance."""

    __tablename__ = "holdings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["external_account_id", "client_id"],
            ["external_accounts.id", "external_accounts.client_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.user_id", ondelete="CASCADE"))
    external_account_id: Mapped[int | None] = mapped_column(BigInteger)
    ticker: Mapped[str] = mapped_column(Text)
    asset_class: Mapped[str] = mapped_column(Text)  # AssetClass
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    maturity_date: Mapped[dt.date | None]
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), server_onupdate=FetchedValue()
    )

    external_account: Mapped[ExternalAccountRecord | None] = relationship(
        back_populates="holdings", lazy="joined"
    )

    @property
    def institution(self) -> str:
        return self.external_account.institution if self.external_account else INTERNAL

    def to_model(self) -> Holding:
        return Holding(
            ticker=self.ticker,
            asset_class=AssetClass(self.asset_class),
            quantity=self.quantity,
            market_value=self.market_value,
            institution=self.institution,
        )


class PortfolioRequestRecord(Base):
    """Pedido de aporte/resgate/rebalanceamento (RF06). O tool update_portfolio grava aqui."""

    __tablename__ = "portfolio_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.user_id", ondelete="CASCADE"))
    request_type: Mapped[str] = mapped_column(Text)  # APORTE | RESGATE | REBALANCEAMENTO | COMPRA | VENDA | OUTRO
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(Text, default="PENDING")  # PENDING | IN_PROGRESS | DONE | REJECTED
    source: Mapped[str] = mapped_column(Text, default="APP")  # APP | CHAT
    chat_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[dt.datetime | None]
