"""Notificações do painel + leitura da view v_client_signals para o DailyAdvisorEngine."""

import datetime as dt
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.core.database import Base
from src.modules.advisor_dashboard.models import ClientSignals, TriggerType

# Limiares dos gatilhos de relacionamento — ajustem à vontade.
FAMILY_DATE_WINDOW_DAYS = 7
INACTIVITY_DAYS = 30


class NotificationRecord(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )  # destinatário
    kind: Mapped[str] = mapped_column(
        Text
    )  # PORTFOLIO_REQUEST | MEETING | MARKET_ALERT ...
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    read_at: Mapped[dt.datetime | None]  # NULL = não lida
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


def load_client_signals(
    session: Session,
    advisor_id: int,
    portfolio_change_pct: dict[int, float] | None = None,
) -> list[ClientSignals]:
    """Monta os ClientSignals de todos os clientes do assessor a partir do banco.

    `portfolio_change_pct` (client_id -> variação % do dia) vem das cotações no
    Redis cruzadas com as posições; o resto sai da view v_client_signals.
    """
    change = portfolio_change_pct or {}
    rows = session.execute(
        text("SELECT * FROM v_client_signals WHERE advisor_id = :a ORDER BY client_id"),
        {"a": advisor_id},
    ).mappings()

    signals = []
    for r in rows:
        triggers: list[TriggerType] = []
        if r["days_to_birthday"] == 0:
            triggers.append(TriggerType.BIRTHDAY)
        if (
            r["days_to_family_date"] is not None
            and r["days_to_family_date"] <= FAMILY_DATE_WINDOW_DAYS
        ):
            triggers.append(TriggerType.FAMILY_DATE)
        if r["days_since_last_contact"] >= INACTIVITY_DAYS:
            triggers.append(TriggerType.INACTIVITY)
        signals.append(
            ClientSignals(
                client_id=r["client_id"],
                portfolio_change_pct=change.get(r["client_id"], 0.0),
                risk_profile=r["risk_profile"],
                relationship_triggers=triggers,
                days_since_last_contact=r["days_since_last_contact"],
            )
        )
    return signals
