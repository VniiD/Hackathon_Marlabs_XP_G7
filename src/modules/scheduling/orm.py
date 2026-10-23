"""Agenda do assessor. O banco recusa reuniões sobrepostas (constraint meetings_no_overlap)."""

import datetime as dt

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.modules.scheduling.models import Meeting, MeetingParty, MeetingStatus, TimeSlot


class AdvisorAvailabilityRecord(Base):
    """Janela semanal de atendimento. find_free_slots = janelas - reuniões."""

    __tablename__ = "advisor_availability"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    advisor_id: Mapped[int] = mapped_column(
        ForeignKey("advisor_profiles.user_id", ondelete="CASCADE")
    )
    weekday: Mapped[int] = mapped_column(
        SmallInteger
    )  # ISO: 1 = segunda ... 7 = domingo
    start_time: Mapped[dt.time]
    end_time: Mapped[dt.time]


class MeetingRecord(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisor_profiles.user_id"))
    client_id: Mapped[int] = mapped_column(
        ForeignKey("client_profiles.user_id", ondelete="CASCADE")
    )
    starts_at: Mapped[dt.datetime]
    ends_at: Mapped[dt.datetime]
    topic: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        Text, default="PENDING"
    )  # PENDING | CONFIRMED | CANCELLED | DONE
    created_via: Mapped[str] = mapped_column(
        Text, default="APP"
    )  # APP | CHAT | ADVISOR
    initiated_by: Mapped[str] = mapped_column(
        Text, default="CLIENT"
    )  # CLIENT | ADVISOR
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    def to_model(self) -> Meeting:
        return Meeting(
            id=self.id,
            client_id=self.client_id,
            advisor_id=self.advisor_id,
            slot=TimeSlot(start=self.starts_at, end=self.ends_at),
            topic=self.topic,
            status=MeetingStatus(self.status),
            initiated_by=MeetingParty(self.initiated_by),
        )
