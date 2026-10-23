from datetime import date as Date
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRole(StrEnum):
    ADVISOR = "ADVISOR"
    CLIENT = "CLIENT"


class RiskProfile(StrEnum):
    CONSERVADOR = "CONSERVADOR"
    MODERADO = "MODERADO"
    ARROJADO = "ARROJADO"


class FamilyDate(BaseModel):
    label: str = Field(examples=["Aniversário da filha"])
    date: Date


class PersonalContext(BaseModel):
    hobbies: list[str] = []
    favorite_team: str | None = None
    family_dates: list[FamilyDate] = []


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    email: str
    role: UserRole


class ClientProfile(BaseModel):
    user: User
    advisor_id: int
    risk_profile: RiskProfile
    context: PersonalContext = PersonalContext()


class ClientCreate(BaseModel):
    name: str
    email: str
    advisor_id: int
    risk_profile: RiskProfile
    context: PersonalContext = PersonalContext()


class SignUpRequest(BaseModel):
    name: str
    email: str


class LoginProfile(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    needs_onboarding: bool = False


class SuitabilityAnswer(BaseModel):
    question_id: str
    answer: str
    option_index: int | None = None


SuitabilityAnswerIn = SuitabilityAnswer


class Suitability(BaseModel):
    client_id: int
    answers: list[SuitabilityAnswer] = []
    risk_profile: RiskProfile | None = None


class AdvisorNote(BaseModel):
    id: int
    client_id: int
    advisor_id: int
    text: str
    created_at: datetime


class AdvisorNoteText(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A anotação não pode ficar vazia.")
        return value
