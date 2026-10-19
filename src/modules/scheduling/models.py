from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class MeetingStatus(StrEnum):
    PENDING = "PENDING"  # aguardando a confirmação da parte que não pediu
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    DONE = "DONE"


class MeetingParty(StrEnum):
    """Lado da reunião; espelha accounts.UserRole sem importar o módulo."""

    CLIENT = "CLIENT"
    ADVISOR = "ADVISOR"


class TimeSlot(BaseModel):
    start: datetime
    end: datetime


class ContextAnswer(BaseModel):
    """Uma resposta do cliente às perguntas feitas pelo copiloto antes de marcar a reunião."""

    key: str
    question: str
    answer: str


class MeetingContext(BaseModel):
    answers: list[ContextAnswer] = []
    summary: str = ""


class MeetingRequest(BaseModel):
    client_id: int
    advisor_id: int
    preferred: TimeSlot | None = None
    topic: str = ""
    initiated_by: MeetingParty = MeetingParty.CLIENT
    context: MeetingContext | None = None


class MeetingConfirm(BaseModel):
    """Quem confirma. Sem auth ainda, vem no corpo; o papel desfaz ids repetidos entre perfis."""

    user_id: int
    role: MeetingParty


class Meeting(BaseModel):
    id: int
    client_id: int
    advisor_id: int
    slot: TimeSlot
    topic: str = ""
    status: MeetingStatus = MeetingStatus.PENDING
    initiated_by: MeetingParty = MeetingParty.CLIENT
    # Preenchido quando o cliente marca pelo chat; reuniões pedidas pelo assessor não têm.
    context: MeetingContext | None = None
