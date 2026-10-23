import datetime as dt
from collections.abc import Iterator

from sqlalchemy import create_engine, DateTime
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa compartilhada pelos modulos (usada pelo Alembic)."""

    # Todo timestamp do 01_schema.sql é TIMESTAMPTZ
    type_annotation_map = {dt.datetime: DateTime(timezone=True)}


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
