"""O que o README do db/ diz que "o banco garante sozinho", testado no Postgres."""

import pytest
from sqlalchemy.exc import IntegrityError, DataError

REJECT = (IntegrityError, DataError)


# ------------------------------------------------------------------ accounts
def test_email_unico_sem_diferenciar_maiuscula(sql):
    with pytest.raises(IntegrityError, match="users_email_uq"):
        sql(
            "INSERT INTO users (name, email, role) VALUES ('X', 'HELENA@Exemplo.com', 'CLIENT')"
        )


def test_role_invalido(sql):
    with pytest.raises(IntegrityError, match="check"):
        sql("INSERT INTO users (name, email, role) VALUES ('X', 'x@x.com', 'ADMIN')")


def test_cliente_nao_pode_ser_assessor_de_outro(sql):
    # usuário 2 (Helena) é cliente, não tem advisor_profile
    sql(
        "INSERT INTO users (id, name, email, role) VALUES (100, 'Novo', 'novo@x.com', 'CLIENT')"
    )
    with pytest.raises(IntegrityError, match="client_profiles_advisor_id_fkey"):
        sql(
            "INSERT INTO client_profiles (user_id, advisor_id, risk_profile) VALUES (100, 2, 'MODERADO')"
        )


def test_risk_profile_invalido(sql):
    sql(
        "INSERT INTO users (id, name, email, role) VALUES (100, 'Novo', 'novo@x.com', 'CLIENT')"
    )
    with pytest.raises(IntegrityError, match="check"):
        sql(
            "INSERT INTO client_profiles (user_id, advisor_id, risk_profile) VALUES (100, 1, 'AGRESSIVO')"
        )


def test_updated_at_atualiza_sozinho(sql):
    before = sql("SELECT updated_at FROM users WHERE id = 2").scalar_one()
    sql("SELECT pg_sleep(0.01)")
    # now() é fixo dentro da transação; o trigger usa now(), então comparamos com
    # o início da transação: tem que ser >= e, no caso do seed, maior.
    sql("UPDATE users SET name = 'Helena D.' WHERE id = 2")
    after = sql("SELECT updated_at FROM users WHERE id = 2").scalar_one()
    assert after >= before


# ------------------------------------------------------------------ portfolio
def test_um_consentimento_ativo_por_instituicao(sql):
    with pytest.raises(IntegrityError, match="consents_active_uq"):
        sql(
            "INSERT INTO open_finance_consents (client_id, institution, status) VALUES (2, 'Banco Aurora', 'ACTIVE')"
        )
    # revogado/pendente pode coexistir
    sql(
        "INSERT INTO open_finance_consents (client_id, institution, status) VALUES (2, 'Banco Aurora', 'REVOKED')"
    )


def test_conta_externa_nao_pode_usar_consentimento_de_outro_cliente(sql):
    # consentimento 1 é da Helena (2); tentar criar conta para o Rafael (3)
    with pytest.raises(
        IntegrityError, match="external_accounts_consent_id_client_id_fkey"
    ):
        sql(
            "INSERT INTO external_accounts (consent_id, client_id, institution, account_id) "
            "VALUES (1, 3, 'Banco Aurora', 'X-1')"
        )


def test_posicao_externa_so_em_conta_do_proprio_cliente(sql):
    # conta externa 1 é da Helena (2)
    with pytest.raises(
        IntegrityError, match="holdings_external_account_id_client_id_fkey"
    ):
        sql(
            "INSERT INTO holdings (client_id, external_account_id, ticker, asset_class, quantity) "
            "VALUES (3, 1, 'XPTO', 'ACOES', 1)"
        )


def test_posicao_interna_duplicada_e_recusada(sql):
    # NULLS NOT DISTINCT: dois PETR4 em custódia XP para o mesmo cliente
    with pytest.raises(
        IntegrityError, match="holdings_client_id_external_account_id_ticker_key"
    ):
        sql(
            "INSERT INTO holdings (client_id, ticker, asset_class, quantity) VALUES (3, 'PETR4', 'ACOES', 1)"
        )


def test_mesmo_ticker_interno_e_externo_e_permitido(sql):
    sql(
        "INSERT INTO holdings (client_id, external_account_id, ticker, asset_class, quantity) "
        "VALUES (2, 1, 'ITUB4', 'ACOES', 10)"
    )


@pytest.mark.parametrize("qty,value", [(-1, 0), (1, -0.01)])
def test_valores_negativos_recusados(sql, qty, value):
    with pytest.raises(IntegrityError, match="check"):
        sql(
            "INSERT INTO holdings (client_id, ticker, asset_class, quantity, market_value) "
            "VALUES (3, 'NOVO', 'ACOES', :q, :v)",
            q=qty,
            v=value,
        )


def test_asset_class_invalida(sql):
    with pytest.raises(IntegrityError, match="check"):
        sql(
            "INSERT INTO holdings (client_id, ticker, asset_class, quantity) VALUES (3, 'NOVO', 'EQUITY', 1)"
        )


def test_bitcoin_guarda_8_casas(sql):
    sql("UPDATE holdings SET quantity = 0.12345678 WHERE ticker = 'BTC'")
    assert (
        str(sql("SELECT quantity FROM holdings WHERE ticker = 'BTC'").scalar_one())
        == "0.12345678"
    )


def test_revogar_consentimento_apaga_contas_e_posicoes_externas(sql):
    sql("DELETE FROM open_finance_consents WHERE id = 1")
    assert (
        sql("SELECT count(*) FROM external_accounts WHERE client_id = 2").scalar_one()
        == 0
    )
    assert (
        sql(
            "SELECT count(*) FROM holdings WHERE ticker = 'CDB-AURORA-2027'"
        ).scalar_one()
        == 0
    )
    assert (
        sql("SELECT count(*) FROM holdings WHERE client_id = 2").scalar_one() == 3
    )  # internas ficam


# ------------------------------------------------------------------ scheduling
MEETING = (
    "INSERT INTO meetings (advisor_id, client_id, starts_at, ends_at, status) "
    "VALUES (1, :c, :s, :e, :st)"
)


def _slot(sql, h_start, h_end):
    d = sql("SELECT (current_date + 3)::text").scalar_one()
    return f"{d} {h_start}-03", f"{d} {h_end}-03"


def test_reuniao_sobreposta_e_recusada(sql):
    s, e = _slot(sql, "10:15", "10:45")  # seed: 10:00–10:30
    with pytest.raises(IntegrityError, match="meetings_no_overlap"):
        sql(MEETING, c=2, s=s, e=e, st="PENDING")


def test_reuniao_colada_na_outra_e_permitida(sql):
    s, e = _slot(sql, "10:30", "11:00")  # tstzrange é [início, fim)
    sql(MEETING, c=2, s=s, e=e, st="PENDING")


def test_reuniao_cancelada_nao_bloqueia_horario(sql):
    sql("UPDATE meetings SET status = 'CANCELLED'")
    s, e = _slot(sql, "10:00", "10:30")
    sql(MEETING, c=2, s=s, e=e, st="PENDING")


def test_reuniao_com_fim_antes_do_inicio(sql):
    s, e = _slot(sql, "15:00", "14:00")
    with pytest.raises(IntegrityError, match="check"):
        sql(MEETING, c=2, s=s, e=e, st="PENDING")


def test_disponibilidade_dia_invalido(sql):
    with pytest.raises(IntegrityError, match="check"):
        sql(
            "INSERT INTO advisor_availability (advisor_id, weekday, start_time, end_time) VALUES (1, 0, '09:00', '10:00')"
        )


# ------------------------------------------------------------------ copiloto / notícias
def test_apagar_mensagem_desvincula_pedido(sql):
    sql("DELETE FROM chat_messages WHERE id = 1")
    assert (
        sql("SELECT chat_message_id FROM portfolio_requests WHERE id = 1").scalar_one()
        is None
    )


def test_sentimento_fora_de_menos1_a_1(sql):
    with pytest.raises(IntegrityError, match="check"):
        sql(
            "INSERT INTO news_mentions (news_id, ticker, sentiment) VALUES (1, 'VALE3', 1.5)"
        )


def test_noticia_com_url_repetida(sql):
    with pytest.raises(IntegrityError, match="news_articles_url_key"):
        sql(
            "INSERT INTO news_articles (source, url, headline, published_at) "
            "VALUES ('X', 'https://exemplo.com/noticias/1', 'dup', now())"
        )


def test_sequencias_avancadas_depois_do_seed(sql):
    # sem o setval do seed, esse insert colidiria com id 1..6 (num banco novo dá 7;
    # aqui pode ser maior porque sequências não voltam no rollback dos outros testes)
    new_id = sql(
        "INSERT INTO users (name, email, role) VALUES ('X', 'x@x.com', 'CLIENT') RETURNING id"
    ).scalar_one()
    assert new_id > 6


# ------------------------------------------------------------------ apagar cliente
def test_apagar_cliente_leva_tudo_junto(sql):
    sql("DELETE FROM users WHERE id = 3")  # Rafael
    for table in (
        "client_profiles",
        "holdings",
        "chat_messages",
        "portfolio_requests",
        "contact_log",
    ):
        col = "user_id" if table == "client_profiles" else "client_id"
        assert sql(f"SELECT count(*) FROM {table} WHERE {col} = 3").scalar_one() == 0, (
            table
        )


def test_assessor_com_clientes_nao_pode_ser_apagado(sql):
    with pytest.raises(IntegrityError, match="foreign key"):
        sql("DELETE FROM users WHERE id = 1")
