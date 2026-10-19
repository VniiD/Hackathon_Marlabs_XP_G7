from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from src.core.database import SessionLocal
from src.core.exceptions import DomainError, NotFoundError
from src.modules.accounts.models import (
    ClientCreate,
    ClientProfile,
    LoginProfile,
    PersonalContext,
    RiskProfile,
    Suitability,
    SuitabilityAnswer,
    User,
    UserRole,
)
from src.modules.accounts.orm import AdvisorProfileRecord, ClientProfileRecord, UserRecord


class AccountsService:
    """Serviço de contas com persistência em PostgreSQL e fallback local."""

    ADVISOR_ID = 1
    ADVISOR_NAME = "Paula Azevedo"
    ADVISOR_EMAIL = "paula@exemplo.com"

    def __init__(self, db: object | None = None) -> None:
        self._clients: dict[int, ClientProfile] = {}
        self._pending_onboarding: set[int] = set()
        self._suitability: dict[int, Suitability] = {}
        self._fallback_mode = False
        self._advisor = LoginProfile(
            id=self.ADVISOR_ID,
            name=self.ADVISOR_NAME,
            email=self.ADVISOR_EMAIL,
            role=UserRole.ADVISOR,
            needs_onboarding=False,
        )
        self._seed_default_advisor()

    def _seed_default_advisor(self) -> None:
        try:
            with SessionLocal() as db:
                advisor = db.get(UserRecord, self.ADVISOR_ID)
                if advisor is None:
                    advisor = UserRecord(
                        id=self.ADVISOR_ID,
                        name=self.ADVISOR_NAME,
                        email=self.ADVISOR_EMAIL,
                        role=UserRole.ADVISOR.value,
                    )
                    db.add(advisor)
                    db.flush()
                    db.add(AdvisorProfileRecord(user_id=self.ADVISOR_ID, crm_code="A10001"))
                    db.commit()
                self._fallback_mode = False
        except OperationalError:
            self._fallback_mode = True

    def _profile_from_client(self, client: ClientProfile, needs_onboarding: bool | None = None) -> LoginProfile:
        return LoginProfile(
            id=client.user.id,
            name=client.user.name,
            email=client.user.email,
            role=client.user.role,
            needs_onboarding=
                needs_onboarding if needs_onboarding is not None else client.user.id in self._pending_onboarding,
        )

    def create_client(self, data: ClientCreate) -> ClientProfile:
        clean_name = data.name.strip()
        clean_email = data.email.strip()
        if not clean_name or not clean_email:
            raise DomainError("Nome e e-mail são obrigatórios.")

        if self._fallback_mode:
            client_id = max([self.ADVISOR_ID, *self._clients.keys()], default=self.ADVISOR_ID) + 1
            profile = ClientProfile(
                user=User(id=client_id, name=clean_name, email=clean_email, role=UserRole.CLIENT),
                advisor_id=data.advisor_id,
                risk_profile=data.risk_profile,
                context=data.context,
            )
            self._clients[client_id] = profile
            return profile

        with SessionLocal() as db:
            existing = db.execute(
                select(UserRecord).where(UserRecord.email.ilike(clean_email))
            ).scalars().first()
            if existing is not None:
                raise DomainError(f"Usuário com e-mail {clean_email} já cadastrado.")

            profile = ClientProfileRecord.from_create(
                ClientCreate(
                    name=clean_name,
                    email=clean_email,
                    advisor_id=data.advisor_id,
                    risk_profile=data.risk_profile,
                    context=data.context,
                )
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            if profile.user is not None:
                db.refresh(profile.user)
            return profile.to_model()

    def sign_up(self, name: str, email: str, advisor_id: int = ADVISOR_ID) -> LoginProfile:
        clean_name = name.strip()
        clean_email = email.strip()
        if not clean_name or not clean_email:
            raise DomainError("Nome e e-mail são obrigatórios.")

        client = self.create_client(
            ClientCreate(
                name=clean_name,
                email=clean_email,
                advisor_id=advisor_id,
                risk_profile=RiskProfile.MODERADO,
                context=PersonalContext(),
            )
        )
        self._pending_onboarding.add(client.user.id)
        return self._profile_from_client(client, needs_onboarding=True)

    def get_client(self, client_id: int) -> ClientProfile:
        if self._fallback_mode:
            try:
                return self._clients[client_id]
            except KeyError:
                raise NotFoundError(f"Cliente {client_id} não encontrado") from None

        with SessionLocal() as db:
            client = db.get(ClientProfileRecord, client_id)
            if client is None:
                raise NotFoundError(f"Cliente {client_id} não encontrado") from None
            return client.to_model()

    def list_clients_by_advisor(self, advisor_id: int) -> list[ClientProfile]:
        if self._fallback_mode:
            return [client for client in self._clients.values() if client.advisor_id == advisor_id]

        with SessionLocal() as db:
            clients = db.execute(
                select(ClientProfileRecord).where(ClientProfileRecord.advisor_id == advisor_id)
            ).scalars().all()
            return [client.to_model() for client in clients]

    def list_profiles(self) -> list[LoginProfile]:
        if self._fallback_mode:
            profiles = [self._advisor]
            profiles.extend(self._profile_from_client(client) for client in self._clients.values())
            return profiles

        with SessionLocal() as db:
            users = db.execute(select(UserRecord).order_by(UserRecord.id)).scalars().all()

        profiles: list[LoginProfile] = []
        for user in users:
            role = UserRole(user.role)
            if role is UserRole.ADVISOR:
                profiles.append(
                    LoginProfile(
                        id=user.id,
                        name=user.name,
                        email=user.email,
                        role=role,
                        needs_onboarding=False,
                    )
                )
                continue
            profiles.append(
                LoginProfile(
                    id=user.id,
                    name=user.name,
                    email=user.email,
                    role=role,
                    needs_onboarding=user.id in self._pending_onboarding,
                )
            )
        return profiles

    def get_suitability(self, client_id: int) -> Suitability:
        client = self.get_client(client_id)
        current = self._suitability.get(client_id)
        if current is None:
            current = Suitability(client_id=client_id, answers=[], risk_profile=client.risk_profile)
            self._suitability[client_id] = current
        return current

    def answer_suitability(self, client_id: int, answer: SuitabilityAnswer) -> Suitability:
        current = self.get_suitability(client_id)
        updated = Suitability(
            client_id=client_id,
            answers=[*current.answers, answer],
            risk_profile=current.risk_profile,
        )
        if len(updated.answers) >= 3:
            updated.risk_profile = self.get_client(client_id).risk_profile
        self._suitability[client_id] = updated
        if updated.risk_profile is not None and client_id in self._pending_onboarding:
            self._pending_onboarding.discard(client_id)
        return updated


_service = AccountsService()


def get_accounts_service() -> AccountsService:
    return _service
