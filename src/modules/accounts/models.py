from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class UserRole(StrEnum):
    ADVISOR = "ADVISOR"
    CLIENT = "CLIENT"


class RiskProfile(StrEnum):
    CONSERVADOR = "CONSERVADOR"
    MODERADO = "MODERADO"
    ARROJADO = "ARROJADO"


class FamilyDate(BaseModel):
    label: str = Field(examples=["Aniversário da filha"])
    date: date


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


class Suitability(BaseModel):
    client_id: int
    answers: list[SuitabilityAnswer] = []
    risk_profile: RiskProfile | None = None
