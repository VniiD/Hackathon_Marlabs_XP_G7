"""Análise de perfil: respostas do questionário e cálculo do perfil de risco."""

import datetime as dt
from typing import cast

from fastapi import Depends
from sqlalchemy import BigInteger, Table, Text, delete, func, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.core.database import Base, get_db
from src.modules.accounts.models import (
    LoginProfile,
    RiskProfile,
    Suitability,
    SuitabilityAnswerIn,
    UserRole,
)
from src.modules.accounts.orm import UserRecord
from src.modules.accounts.services import AccountsService, get_accounts_service

# Perguntas com escolha rápida (0 a 2 pontos); espelha web/src/questions.ts.
REQUIRED_QUESTIONS = ("objetivos", "experiencia", "risco")


class SuitabilityAnswerRecord(Base):
    __tablename__ = "suitability_answers"

    # Sem FK para users: a tabela é criada pela API, fora do db/01_schema.sql.
    client_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question_id: Mapped[str] = mapped_column(Text, primary_key=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    option_index: Mapped[int | None]
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class FirstAccessRecord(Base):
    """Contas criadas pelo cliente: só entram na plataforma depois da análise de perfil."""

    __tablename__ = "suitability_first_access"

    client_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


# Helena já chega com a análise respondida, para o assessor ter o que ler.
_DEMO_EMAIL = "helena@exemplo.com"
_DEMO_ANSWERS = [
    (
        "objetivos",
        0,
        "Quero preservar o que juntei e complementar a aposentadoria. Preciso de uns R$ 8 mil por mês de renda e não posso correr o risco de perder o principal.",
    ),
    (
        "experiencia",
        0,
        "Sempre investi em poupança e CDB pelo banco, há mais de 20 anos. As ações do Itaú eu herdei; nunca decidi sozinha onde aplicar.",
    ),
    (
        "risco",
        0,
        "Fico nervosa quando vejo o saldo cair. Aceito perder no máximo 5% em um ano e preciso de R$ 50 mil disponíveis para resgatar rápido.",
    ),
    (
        "renda",
        None,
        "Sou aposentada, recebo R$ 9 mil do INSS e da previdência, mais R$ 3,5 mil de aluguel de um apartamento. É uma renda estável e consigo guardar uns R$ 2 mil por mês.",
    ),
]
# Cliente de demonstração que ainda não fez a análise de perfil.
_DEMO_NEW_CLIENT = ("Marina Sales", "marina@exemplo.com")


def ensure_tables(db: Session, accounts: AccountsService) -> None:
    """Cria as tabelas no primeiro uso e carrega os dados de demonstração."""
    bind = db.get_bind()
    if inspect(bind).has_table(FirstAccessRecord.__tablename__):
        return
    fresh = not inspect(bind).has_table(SuitabilityAnswerRecord.__tablename__)
    Base.metadata.create_all(
        bind,
        tables=[
            cast(Table, SuitabilityAnswerRecord.__table__),
            cast(Table, FirstAccessRecord.__table__),
        ],
    )
    if not inspect(bind).has_table(UserRecord.__tablename__):
        return
    by_email = {u.email: u.id for u in accounts.list_users()}
    if fresh and _DEMO_EMAIL in by_email:
        db.add_all(
            SuitabilityAnswerRecord(
                client_id=by_email[_DEMO_EMAIL], question_id=q, option_index=o, answer=a
            )
            for q, o, a in _DEMO_ANSWERS
        )
    name, email = _DEMO_NEW_CLIENT
    if email not in by_email and any(
        u.role == UserRole.ADVISOR for u in accounts.list_users()
    ):
        db.add(FirstAccessRecord(client_id=accounts.sign_up(name, email).id))
    db.commit()


def score_profile(answers: list[SuitabilityAnswerIn]) -> RiskProfile | None:
    by_id = {a.question_id: a for a in answers}
    if any(
        by_id.get(q) is None or by_id[q].option_index is None
        for q in REQUIRED_QUESTIONS
    ):
        return None
    points = sum(by_id[q].option_index or 0 for q in REQUIRED_QUESTIONS)
    if points <= 2:
        return RiskProfile.CONSERVADOR
    return RiskProfile.MODERADO if points <= 4 else RiskProfile.ARROJADO


class SuitabilityService:
    def __init__(self, db: Session, accounts: AccountsService) -> None:
        self._db = db
        self._accounts = accounts
        ensure_tables(db, accounts)

    def _rows(self, client_id: int | None = None) -> list[SuitabilityAnswerRecord]:
        query = select(SuitabilityAnswerRecord).order_by(
            SuitabilityAnswerRecord.updated_at
        )
        if client_id is not None:
            query = query.where(SuitabilityAnswerRecord.client_id == client_id)
        return list(self._db.scalars(query))

    def _build(
        self, client_id: int, rows: list[SuitabilityAnswerRecord]
    ) -> Suitability:
        answers = [
            SuitabilityAnswerIn(
                question_id=r.question_id, answer=r.answer, option_index=r.option_index
            )
            for r in rows
        ]
        profile = score_profile(answers)
        if profile is None and not self._is_first_access(client_id):
            # Cliente antigo: vale o perfil do cadastro até ele refazer a análise.
            client = self._accounts.find_client(client_id)
            profile = client.risk_profile if client else None
        return Suitability(client_id=client_id, answers=answers, risk_profile=profile)

    def _is_first_access(self, client_id: int) -> bool:
        return self._db.get(FirstAccessRecord, client_id) is not None

    def get(self, client_id: int) -> Suitability:
        return self._build(client_id, self._rows(client_id))

    def list_all(self) -> list[Suitability]:
        by_client: dict[int, list[SuitabilityAnswerRecord]] = {}
        for row in self._rows():
            by_client.setdefault(row.client_id, []).append(row)
        return [self._build(client_id, rows) for client_id, rows in by_client.items()]

    def answer(self, client_id: int, data: SuitabilityAnswerIn) -> Suitability:
        row = self._db.get(SuitabilityAnswerRecord, (client_id, data.question_id))
        if row is None:
            row = SuitabilityAnswerRecord(
                client_id=client_id, question_id=data.question_id
            )
            self._db.add(row)
        row.answer = data.answer.strip()
        row.option_index = data.option_index
        self._db.commit()
        suitability = self.get(client_id)
        if suitability.risk_profile is not None:
            self._accounts.set_risk_profile(client_id, suitability.risk_profile)
        return suitability

    def clear(self, client_id: int, question_id: str | None = None) -> Suitability:
        """Apaga uma resposta, ou todas quando `question_id` é None."""
        query = delete(SuitabilityAnswerRecord).where(
            SuitabilityAnswerRecord.client_id == client_id
        )
        if question_id is not None:
            query = query.where(SuitabilityAnswerRecord.question_id == question_id)
        self._db.execute(query)
        self._db.commit()
        return self.get(client_id)

    def sign_up(self, name: str, email: str) -> LoginProfile:
        client = self._accounts.sign_up(name, email)
        self._db.add(FirstAccessRecord(client_id=client.id))
        self._db.commit()
        return client

    def login_profiles(self) -> list[LoginProfile]:
        """Todos os usuários, marcando quem ainda precisa fazer a análise de perfil."""
        first_access = set(self._db.scalars(select(FirstAccessRecord.client_id)))
        done = {s.client_id for s in self.list_all() if s.risk_profile is not None}
        return [
            LoginProfile(
                **u.model_dump(),
                needs_onboarding=u.role == UserRole.CLIENT
                and u.id in first_access
                and u.id not in done,
            )
            for u in self._accounts.list_users()
        ]


def get_suitability_service(
    db: Session = Depends(get_db),
    accounts: AccountsService = Depends(get_accounts_service),
) -> SuitabilityService:
    return SuitabilityService(db, accounts)
