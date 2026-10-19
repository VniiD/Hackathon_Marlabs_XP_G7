"""Anotações pessoais do assessor sobre cada cliente (estilo post-it)."""

import datetime as dt

from fastapi import Depends
from sqlalchemy import BigInteger, ForeignKey, Text, func, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.core.database import Base, get_db
from src.core.exceptions import NotFoundError
from src.modules.accounts.models import AdvisorNote
from src.modules.accounts.orm import ClientProfileRecord, UserRecord


class AdvisorNoteRecord(Base):
    __tablename__ = "advisor_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    def to_model(self) -> AdvisorNote:
        return AdvisorNote(
            id=self.id,
            client_id=self.client_id,
            advisor_id=self.advisor_id,
            text=self.text,
            created_at=self.created_at,
        )


def _seed_from_profiles(db: Session) -> None:
    """Na criação da tabela, o antigo contexto fixo (hobbies, time, datas) vira anotação."""
    today = dt.datetime.now()
    for age, client in enumerate(db.scalars(select(ClientProfileRecord)), start=1):
        texts = []
        if client.hobbies:
            texts.append("Gosta de " + " e ".join(h.lower() for h in client.hobbies))
        if client.favorite_team:
            texts.append(f"Torce para o {client.favorite_team}")
        texts += [f"{d.label} em {d.event_date:%d/%m}" for d in client.family_dates]
        for offset, text in enumerate(texts):
            db.add(
                AdvisorNoteRecord(
                    client_id=client.user_id,
                    advisor_id=client.advisor_id,
                    text=text,
                    # Datas espalhadas no passado, como anotações feitas aos poucos.
                    created_at=today - dt.timedelta(days=9 * age + 16 * offset),
                )
            )
    db.commit()


def ensure_table(db: Session) -> None:
    bind = db.get_bind()
    if inspect(bind).has_table(AdvisorNoteRecord.__tablename__):
        return
    AdvisorNoteRecord.__table__.create(bind, checkfirst=True)
    _seed_from_profiles(db)


class NotesService:
    def __init__(self, db: Session) -> None:
        self._db = db
        ensure_table(db)

    def list_for_client(self, client_id: int) -> list[AdvisorNote]:
        query = (
            select(AdvisorNoteRecord)
            .where(AdvisorNoteRecord.client_id == client_id)
            .order_by(AdvisorNoteRecord.created_at.desc(), AdvisorNoteRecord.id.desc())
        )
        return [r.to_model() for r in self._db.scalars(query)]

    def add(self, client_id: int, advisor_id: int, text: str) -> AdvisorNote:
        for user_id, label in ((client_id, "Cliente"), (advisor_id, "Assessor")):
            if self._db.get(UserRecord, user_id) is None:
                raise NotFoundError(f"{label} {user_id} não encontrado")
        record = AdvisorNoteRecord(client_id=client_id, advisor_id=advisor_id, text=text.strip())
        self._db.add(record)
        self._db.commit()
        return record.to_model()

    def _get(self, note_id: int) -> AdvisorNoteRecord:
        record = self._db.get(AdvisorNoteRecord, note_id)
        if record is None:
            raise NotFoundError(f"Anotação {note_id} não encontrada")
        return record

    def edit(self, note_id: int, text: str) -> AdvisorNote:
        record = self._get(note_id)
        record.text = text.strip()
        self._db.commit()
        return record.to_model()

    def delete(self, note_id: int) -> None:
        self._db.delete(self._get(note_id))
        self._db.commit()


def get_notes_service(db: Session = Depends(get_db)) -> NotesService:
    return NotesService(db)
