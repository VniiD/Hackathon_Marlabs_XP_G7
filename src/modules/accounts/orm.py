"""Tabelas do módulo accounts. Esquema canônico: db/01_schema.sql."""

import datetime as dt

from sqlalchemy import BigInteger, FetchedValue, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.modules.accounts.models import (
    ClientCreate,
    ClientProfile,
    FamilyDate,
    PersonalContext,
    RiskProfile,
    User,
    UserRole,
)


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)  # UserRole
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), server_onupdate=FetchedValue()
    )

    client_profile: Mapped["ClientProfileRecord | None"] = relationship(back_populates="user")

    def to_model(self) -> User:
        return User(id=self.id, name=self.name, email=self.email, role=UserRole(self.role))


class AdvisorProfileRecord(Base):
    __tablename__ = "advisor_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    crm_code: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, default="America/Sao_Paulo")

    user: Mapped[UserRecord] = relationship()


class ClientProfileRecord(Base):
    __tablename__ = "client_profiles"

    # user_id é o client_id usado em toda a API.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisor_profiles.user_id"))
    risk_profile: Mapped[str] = mapped_column(Text)  # RiskProfile
    birth_date: Mapped[dt.date | None]
    favorite_team: Mapped[str | None] = mapped_column(Text)
    hobbies: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), server_onupdate=FetchedValue()
    )

    user: Mapped[UserRecord] = relationship(back_populates="client_profile", lazy="joined")
    family_dates: Mapped[list["FamilyDateRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="FamilyDateRecord.event_date", lazy="selectin"
    )

    @property
    def client_id(self) -> int:
        return self.user_id

    def to_model(self) -> ClientProfile:
        return ClientProfile(
            user=self.user.to_model(),
            advisor_id=self.advisor_id,
            risk_profile=RiskProfile(self.risk_profile),
            context=PersonalContext(
                hobbies=list(self.hobbies),
                favorite_team=self.favorite_team,
                family_dates=[FamilyDate(label=f.label, date=f.event_date) for f in self.family_dates],
            ),
        )

    @classmethod
    def from_create(cls, data: ClientCreate) -> "ClientProfileRecord":
        """Monta usuário + perfil + datas a partir do payload de POST /accounts/clients."""
        return cls(
            user=UserRecord(name=data.name, email=data.email, role=UserRole.CLIENT.value),
            advisor_id=data.advisor_id,
            risk_profile=data.risk_profile.value,
            favorite_team=data.context.favorite_team,
            hobbies=list(data.context.hobbies),
            family_dates=[
                FamilyDateRecord(label=f.label, event_date=f.date) for f in data.context.family_dates
            ],
        )


class FamilyDateRecord(Base):
    __tablename__ = "family_dates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.user_id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(Text)
    event_date: Mapped[dt.date]
    recurring: Mapped[bool] = mapped_column(default=True)


class ContactLogRecord(Base):
    """CRM: cada contato do assessor com o cliente (alimenta o gatilho INACTIVITY)."""

    __tablename__ = "contact_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.user_id", ondelete="CASCADE"))
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisor_profiles.user_id"))
    channel: Mapped[str] = mapped_column(Text)  # CALL | WHATSAPP | EMAIL | MEETING | OTHER
    summary: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
