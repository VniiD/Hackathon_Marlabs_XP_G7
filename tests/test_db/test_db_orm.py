"""Os orm.py contra o banco real: leitura, escrita, to_model() e o casamento
entre o que o SQLAlchemy acha que existe e o que o 01_schema.sql criou."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from src.core.database import Base
from src.modules.accounts.models import ClientCreate, FamilyDate, PersonalContext, RiskProfile
from src.modules.accounts.orm import ClientProfileRecord, ContactLogRecord, UserRecord
from src.modules.advisor_dashboard.engine import DailyAdvisorEngine
from src.modules.advisor_dashboard.orm import NotificationRecord, load_client_signals
from src.modules.copilot_chat.orm import ChatMessageRecord
from src.modules.market_intelligence.orm import NewsArticleRecord, NewsMentionRecord
from src.modules.portfolio.orm import (
    ExternalAccountRecord,
    HoldingRecord,
    OpenFinanceConsentRecord,
    PortfolioRequestRecord,
)
from src.modules.scheduling.orm import AdvisorAvailabilityRecord, MeetingRecord


# ------------------------------------------------------------------ esquema x ORM
def test_toda_coluna_do_orm_existe_no_banco_com_mesma_nulabilidade(db):
    insp = inspect(db.connection())
    problems = []
    for table in Base.metadata.sorted_tables:
        db_cols = {c["name"]: c for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in db_cols:
                problems.append(f"{table.name}.{col.name}: não existe no banco")
            elif col.nullable != db_cols[col.name]["nullable"] and not col.primary_key:
                problems.append(f"{table.name}.{col.name}: nullable ORM={col.nullable} banco={db_cols[col.name]['nullable']}")
        for name in db_cols.keys() - {c.name for c in table.columns}:
            problems.append(f"{table.name}.{name}: existe no banco mas não no ORM")
    assert problems == []


def test_tipos_de_data_hora_batem(db):
    """No banco todo timestamp é TIMESTAMPTZ. Mapped[dt.datetime] sem
    DateTime(timezone=True) vira TIMESTAMP sem fuso para o SQLAlchemy/Alembic."""
    insp = inspect(db.connection())
    mismatches = []
    for table in Base.metadata.sorted_tables:
        db_cols = {c["name"]: c for c in insp.get_columns(table.name)}
        for col in table.columns:
            db_type = db_cols[col.name]["type"]
            if getattr(db_type, "timezone", None) and not getattr(col.type, "timezone", True):
                mismatches.append(f"{table.name}.{col.name}")
    assert mismatches == [], f"{len(mismatches)} colunas TIMESTAMPTZ mapeadas sem fuso: {mismatches}"


# ------------------------------------------------------------------ leitura
def test_le_todos_os_registros_do_seed(db):
    counts = {
        UserRecord: 6, ClientProfileRecord: 5, ContactLogRecord: 5,
        OpenFinanceConsentRecord: 2, ExternalAccountRecord: 2, HoldingRecord: 13,
        PortfolioRequestRecord: 1, MeetingRecord: 1, AdvisorAvailabilityRecord: 10,
        ChatMessageRecord: 2, NotificationRecord: 1, NewsArticleRecord: 3, NewsMentionRecord: 5,
    }
    for model, n in counts.items():
        assert len(db.scalars(select(model)).all()) == n, model.__name__


def test_cliente_to_model(db):
    helena = db.get(ClientProfileRecord, 2).to_model()
    assert helena.user.name == "Helena Duarte"
    assert helena.risk_profile is RiskProfile.CONSERVADOR
    assert helena.context.hobbies == ["Jardinagem", "Viagens"]
    assert helena.context.family_dates[0].date == dt.date(2026, 10, 18)


def test_holdings_to_model_com_instituicao(db):
    hs = {h.ticker: h.to_model() for h in db.scalars(select(HoldingRecord).where(HoldingRecord.client_id == 2))}
    assert hs["ITUB4"].institution == "INTERNAL"
    assert hs["CDB-AURORA-2027"].institution == "Banco Aurora"
    assert hs["ITUB4"].market_value == Decimal("112640.00")


def test_conta_externa_to_model_traz_posicoes(db):
    acc = db.get(ExternalAccountRecord, 1).to_model()
    assert acc.balance == Decimal("84500.00")
    assert [h.ticker for h in acc.holdings] == ["CDB-AURORA-2027"]
    assert db.get(ExternalAccountRecord, 1).consent.status == "ACTIVE"


def test_reuniao_to_model_com_fuso(db):
    m = db.scalars(select(MeetingRecord)).one().to_model()
    assert m.slot.start.utcoffset() is not None  # veio com fuso
    assert m.slot.end - m.slot.start == dt.timedelta(minutes=30)


def test_noticia_com_mencoes(db):
    art = db.get(NewsArticleRecord, 2)
    assert {m.ticker: round(m.sentiment, 2) for m in art.mentions} == {"ITUB4": -0.6, "BBAS3": -0.4, "BANCOS": -0.5}


# ------------------------------------------------------------------ escrita
def test_from_create_grava_usuario_perfil_e_datas(db):
    data = ClientCreate(
        name="Ana", email="ana@x.com", advisor_id=1, risk_profile=RiskProfile.ARROJADO,
        context=PersonalContext(hobbies=["Surfe"], family_dates=[FamilyDate(label="Filho", date=dt.date(2020, 5, 1))]),
    )
    rec = ClientProfileRecord.from_create(data)
    db.add(rec)
    db.flush()
    assert rec.user_id > 6  # sequência continuou depois do seed
    db.expire_all()
    back = db.get(ClientProfileRecord, rec.user_id).to_model()
    assert back.user.email == "ana@x.com" and back.context.family_dates[0].label == "Filho"


def test_from_create_com_assessor_inexistente_falha(db):
    """É o que o tests/test_smoke.py faz (advisor_id=99) — passa em memória, quebra no banco."""
    db.add(ClientProfileRecord.from_create(
        ClientCreate(name="Ana", email="a@x.com", advisor_id=99, risk_profile=RiskProfile.CONSERVADOR)
    ))
    with pytest.raises(IntegrityError, match="advisor_id"):
        db.flush()


def test_from_create_com_email_repetido_falha(db):
    db.add(ClientProfileRecord.from_create(
        ClientCreate(name="Outra Helena", email="Helena@exemplo.com", advisor_id=1, risk_profile=RiskProfile.MODERADO)
    ))
    with pytest.raises(IntegrityError, match="users_email_uq"):
        db.flush()


def test_hobbies_mutavel_e_persistido(db):
    rec = db.get(ClientProfileRecord, 3)
    rec.hobbies.append("Xadrez")
    db.flush()
    db.expire_all()
    assert db.get(ClientProfileRecord, 3).hobbies == ["Ciclismo", "Vinhos", "Xadrez"]


def test_posicao_externa_via_relacionamento_herda_client_id(db):
    acc = db.get(ExternalAccountRecord, 2)  # Beatriz, Corretora Litoral
    acc.holdings.append(HoldingRecord(client_id=4, ticker="LCI-LIT", asset_class="RENDA_FIXA", quantity=Decimal(1),
                                      market_value=Decimal("10000")))
    db.flush()
    h = db.scalars(select(HoldingRecord).where(HoldingRecord.ticker == "LCI-LIT")).one()
    assert h.external_account_id == 2 and h.institution == "Corretora Litoral"


def test_reuniao_sobreposta_pelo_orm(db):
    seed = db.scalars(select(MeetingRecord)).one()
    db.add(MeetingRecord(advisor_id=1, client_id=2, starts_at=seed.starts_at + dt.timedelta(minutes=10),
                         ends_at=seed.ends_at + dt.timedelta(minutes=10)))
    with pytest.raises(IntegrityError, match="meetings_no_overlap"):
        db.flush()


def test_reuniao_nova_pelo_orm_com_defaults(db):
    start = dt.datetime(2030, 1, 7, 14, 0, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
    m = MeetingRecord(advisor_id=1, client_id=2, starts_at=start, ends_at=start + dt.timedelta(minutes=30))
    db.add(m)
    db.flush()
    db.refresh(m)
    assert (m.status, m.created_via, m.topic) == ("PENDING", "APP", "")
    assert m.to_model().slot.start == start


def test_pedido_de_carteira_pelo_orm(db):
    msg = ChatMessageRecord(client_id=6, role="USER", content="Quero resgatar o CDB", input_mode="VOICE")
    db.add(msg)
    db.flush()
    req = PortfolioRequestRecord(client_id=6, request_type="RESGATE", details={"ticker": "CDB-XP-2026"},
                                 source="CHAT", chat_message_id=msg.id)
    db.add(req)
    db.flush()
    db.refresh(req)
    assert req.status == "PENDING" and req.details == {"ticker": "CDB-XP-2026"}
    assert msg.tool_calls == []


def test_notificacao_pelo_orm(db):
    n = NotificationRecord(user_id=1, kind="MEETING", title="Nova reunião")
    db.add(n)
    db.flush()
    db.refresh(n)
    assert n.payload == {} and n.read_at is None


def test_updated_at_do_orm_recarrega_valor_do_trigger(db):
    h = db.scalars(select(HoldingRecord).where(HoldingRecord.ticker == "PETR4")).one()
    h.market_value = Decimal("350000")
    db.flush()
    assert isinstance(h.updated_at, dt.datetime)  # FetchedValue: relê do banco sem erro


# ------------------------------------------------------------------ motor
def test_fila_do_dia_igual_ao_readme(db):
    signals = load_client_signals(db, advisor_id=1, portfolio_change_pct={2: -4.2})
    ranked = DailyAdvisorEngine().prioritize(signals)
    got = [(round(p.criticality_score, 1), p.client_id, p.next_best_action.title) for p in ranked]
    assert got == [
        (65.0, 2, "Ligar para acalmar e revisar exposição"),
        (23.7, 4, "Contato de acompanhamento"),
        (16.7, 5, "Enviar felicitações"),
        (5.0, 6, "Contato de acompanhamento"),
        (4.0, 3, "Contato de acompanhamento"),
    ]


def test_assessor_sem_clientes(db):
    assert load_client_signals(db, advisor_id=12345) == []
