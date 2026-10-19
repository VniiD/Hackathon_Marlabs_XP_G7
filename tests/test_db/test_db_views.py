"""Views e a função next_occurrence."""

import datetime as dt
from decimal import Decimal

import pytest


@pytest.mark.parametrize(
    "birth,ref,expected",
    [
        ("1958-03-14", "2026-10-10", "2027-03-14"),  # já passou este ano -> ano que vem
        ("1979-12-05", "2026-10-10", "2026-12-05"),  # ainda vai acontecer
        ("1990-10-10", "2026-10-10", "2026-10-10"),  # hoje
        ("2000-02-29", "2027-01-01", "2027-02-28"),  # 29/02 em ano não bissexto
        ("2000-02-29", "2028-01-01", "2028-02-29"),  # 29/02 em ano bissexto
        ("2000-02-29", "2027-03-01", "2028-02-29"),  # já passou -> próximo, bissexto
        ("1980-12-31", "2026-12-31", "2026-12-31"),
    ],
)
def test_next_occurrence(sql, birth, ref, expected):
    got = sql("SELECT next_occurrence(CAST(:b AS date), CAST(:r AS date))", b=birth, r=ref).scalar_one()
    assert got == dt.date.fromisoformat(expected)


def test_patrimonio_total_igual_ao_test_smoke(sql):
    assert sql("SELECT sum(total_net_worth) FROM v_client_net_worth").scalar_one() == Decimal("3242300.00")


def test_patrimonio_por_cliente(sql):
    rows = dict(sql("SELECT client_id, total_net_worth FROM v_client_net_worth").all())
    assert rows == {
        2: Decimal("1198440.00"),  # 864k custódia + 250k CDB externo + 84,5k saldo
        3: Decimal("799150.00"),
        4: Decimal("522110.00"),
        5: Decimal("252200.00"),
        6: Decimal("470400.00"),
    }


def test_alocacao_fecha_100_por_cento(sql):
    for cid, total in sql("SELECT client_id, sum(pct) FROM v_client_allocation GROUP BY 1").all():
        assert abs(total - 100) <= Decimal("0.02"), cid


def test_cliente_sem_posicoes_aparece_com_zero(sql):
    sql("INSERT INTO users (id, name, email, role) VALUES (100, 'Novo', 'novo@x.com', 'CLIENT')")
    sql("INSERT INTO client_profiles (user_id, advisor_id, risk_profile) VALUES (100, 1, 'MODERADO')")
    row = sql("SELECT * FROM v_client_signals WHERE client_id = 100").mappings().one()
    assert row["total_net_worth"] == 0
    assert row["days_since_last_contact"] == 0  # sem contato -> conta a partir do cadastro
    assert row["days_to_birthday"] is None
    assert row["open_requests"] == 0


def test_sinais_do_seed(sql):
    rows = {r["client_id"]: r for r in sql("SELECT * FROM v_client_signals").mappings()}
    assert rows[5]["days_to_birthday"] == 0                       # Otávio: aniversário hoje
    assert rows[4]["days_since_last_contact"] == 41               # Beatriz: 41 dias
    assert rows[6]["next_maturity_ticker"] == "CDB-XP-2026"       # Camila
    assert rows[6]["days_to_maturity"] == 9
    assert rows[2]["next_maturity_ticker"] == "CDB-AURORA-2027"   # externo vence antes do Tesouro
    assert rows[3]["open_requests"] == 1                          # Rafael: aporte pendente
    assert rows[5]["next_meeting_at"] is not None


def test_pedido_resolvido_sai_da_contagem(sql):
    sql("UPDATE portfolio_requests SET status = 'DONE', resolved_at = now() WHERE id = 1")
    assert sql("SELECT open_requests FROM v_client_signals WHERE client_id = 3").scalar_one() == 0


def test_data_familiar_nao_recorrente_que_ja_passou_some(sql):
    sql("INSERT INTO family_dates (client_id, label, event_date, recurring) "
        "VALUES (3, 'Formatura', current_date - 1, false)")
    assert sql("SELECT next_family_date_label FROM v_client_signals WHERE client_id = 3").scalar_one() is None


def test_data_familiar_mais_proxima_vence(sql):
    sql("INSERT INTO family_dates (client_id, label, event_date) VALUES (2, 'Casamento da filha', current_date + 2)")
    row = sql("SELECT next_family_date_label, days_to_family_date FROM v_client_signals WHERE client_id = 2").one()
    assert tuple(row) == ("Casamento da filha", 2)
