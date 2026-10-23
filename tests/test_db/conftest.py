"""Testes contra o Postgres real. Cada teste roda numa transação desfeita no fim,
então o banco com o seed fica intacto entre um teste e outro."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Padrão: o Postgres do docker compose. Sobrescreva com DATABASE_URL se precisar.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/advisor"
)

# Registra todas as tabelas no Base.metadata.
import src.modules.accounts.orm  # noqa: E402,F401
import src.modules.accounts.notes  # noqa: E402,F401
from src.modules.accounts.notes import NotesService  # noqa: E402
import src.modules.advisor_dashboard.orm  # noqa: E402,F401
import src.modules.copilot_chat.orm  # noqa: E402,F401
import src.modules.market_intelligence.orm  # noqa: E402,F401
import src.modules.portfolio.orm  # noqa: E402,F401
import src.modules.scheduling.orm  # noqa: E402,F401


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(os.environ["DATABASE_URL"])
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    NotesService(session)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def sql(db):
    """Executa SQL cru dentro de um savepoint, para conseguir testar erros sem
    perder a transação do teste."""

    def run(stmt: str, **params):
        with db.begin_nested():
            return db.execute(text(stmt), params)

    return run
