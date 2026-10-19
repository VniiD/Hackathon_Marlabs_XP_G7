-- =============================================================================
-- Dados de demonstração — os mesmos clientes, carteiras e contas do
-- web/src/api/mock.ts, para a UI ficar igual com VITE_USE_MOCKS=false.
--
-- IDs: assessor = 1 (CURRENT_ADVISOR_ID do front); clientes = 2..6
-- (no mock eram 1..5; aqui assessor e clientes dividem a tabela users).
--
-- Datas relativas a current_date/now() para os gatilhos funcionarem no dia
-- em que o banco for criado (aniversário hoje, CDB vencendo em 9 dias...).
-- Senha de todos os usuários: senha123 (bcrypt, verificável com bcrypt.checkpw).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- só para gerar o hash bcrypt do seed

BEGIN;

-- ---------------------------------------------------------------- usuários
INSERT INTO users (id, name, email, password_hash, role) VALUES
    (1, 'Marina Azevedo',   'assessor@exemplo.com', crypt('senha123', gen_salt('bf', 10)), 'ADVISOR'),
    (2, 'Helena Duarte',    'helena@exemplo.com',   crypt('senha123', gen_salt('bf', 10)), 'CLIENT'),
    (3, 'Rafael Monteiro',  'rafael@exemplo.com',   crypt('senha123', gen_salt('bf', 10)), 'CLIENT'),
    (4, 'Beatriz Nogueira', 'beatriz@exemplo.com',  crypt('senha123', gen_salt('bf', 10)), 'CLIENT'),
    (5, 'Otávio Lins',      'otavio@exemplo.com',   crypt('senha123', gen_salt('bf', 10)), 'CLIENT'),
    (6, 'Camila Prates',    'camila@exemplo.com',   crypt('senha123', gen_salt('bf', 10)), 'CLIENT');

INSERT INTO advisor_profiles (user_id, crm_code) VALUES (1, 'A10001');

INSERT INTO client_profiles (user_id, advisor_id, risk_profile, birth_date, favorite_team, hobbies, created_at) VALUES
    (2, 1, 'CONSERVADOR', DATE '1958-03-14',                        'Palmeiras',   '{Jardinagem,Viagens}', now() - interval '3 years'),
    (3, 1, 'ARROJADO',    DATE '1987-07-22',                        'Flamengo',    '{Ciclismo,Vinhos}',    now() - interval '2 years'),
    (4, 1, 'MODERADO',    DATE '1979-12-05',                        NULL,          '{Corrida}',            now() - interval '1 year'),
    (5, 1, 'MODERADO',    (current_date - interval '61 years')::date, 'Grêmio',    '{Pesca,Golfe}',        now() - interval '4 years'),  -- aniversário hoje
    (6, 1, 'CONSERVADOR', DATE '1966-05-30',                        'Corinthians', '{Leitura}',            now() - interval '5 years');

INSERT INTO family_dates (client_id, label, event_date) VALUES
    (2, 'Aniversário do neto',      DATE '2026-10-18'),
    (4, 'Aniversário de casamento', DATE '2026-11-02');

INSERT INTO contact_log (client_id, advisor_id, channel, summary, occurred_at) VALUES
    (2, 1, 'CALL',     'Revisão trimestral da carteira',             now() - interval '6 days'),
    (3, 1, 'WHATSAPP', 'Comentou interesse em aumentar cripto',      now() - interval '12 days'),
    (4, 1, 'MEETING',  'Reunião de planejamento anual',              now() - interval '41 days'),
    (5, 1, 'EMAIL',    'Envio do relatório mensal',                  now() - interval '20 days'),
    (6, 1, 'CALL',     'Conversa sobre o vencimento do CDB',         now() - interval '15 days');

-- ---------------------------------------------------------------- Open Finance
INSERT INTO open_finance_consents (id, client_id, institution, external_consent_id, status, permissions, granted_at, expires_at) VALUES
    (1, 2, 'Banco Aurora',      'urn:aurora:consent:7f3a', 'ACTIVE', '{ACCOUNTS_READ,ACCOUNTS_BALANCES_READ,INVESTMENTS_READ}', now() - interval '30 days', now() + interval '335 days'),
    (2, 4, 'Corretora Litoral', 'urn:litoral:consent:91c2', 'ACTIVE', '{ACCOUNTS_READ,ACCOUNTS_BALANCES_READ}',                 now() - interval '60 days', now() + interval '305 days');

INSERT INTO external_accounts (id, consent_id, client_id, institution, account_id, balance) VALUES
    (1, 1, 2, 'Banco Aurora',      'AUR-0098', 84500.00),
    (2, 2, 4, 'Corretora Litoral', 'LIT-4471', 32100.00);

-- ---------------------------------------------------------------- posições
-- external_account_id NULL = custódia XP ("INTERNAL" no Holding)
INSERT INTO holdings (client_id, external_account_id, ticker, asset_class, quantity, average_price, market_value, maturity_date) VALUES
    -- Helena (conservadora)
    (2, NULL, 'TESOURO-SELIC-2029', 'RENDA_FIXA', 42,   NULL,      610000.00, DATE '2029-03-01'),
    (2, NULL, 'ITUB4',              'ACOES',      3200, 32.80,     112640.00, NULL),
    (2, NULL, 'KNRI11',             'FUNDOS',     900,  150.20,    141300.00, NULL),
    (2, 1,    'CDB-AURORA-2027',    'RENDA_FIXA', 1,    NULL,      250000.00, DATE '2027-06-15'),
    -- Rafael (arrojado)
    (3, NULL, 'PETR4',              'ACOES',      9000, 34.90,     342900.00, NULL),
    (3, NULL, 'VALE3',              'ACOES',      2500, 68.10,     158750.00, NULL),
    (3, NULL, 'BTC',                'CRIPTO',     0.85, 290000.00, 297500.00, NULL),
    -- Beatriz (moderada)
    (4, NULL, 'WEGE3',              'ACOES',      4100, 41.30,     221810.00, NULL),
    (4, NULL, 'TESOURO-IPCA-2035',  'RENDA_FIXA', 60,   NULL,      268200.00, DATE '2035-05-15'),
    -- Otávio (moderado)
    (5, NULL, 'BBAS3',              'ACOES',      5000, 26.40,     139500.00, NULL),
    (5, NULL, 'HGLG11',             'FUNDOS',     700,  158.00,    112700.00, NULL),
    -- Camila (conservadora) — CDB vence em 9 dias
    (6, NULL, 'CDB-XP-2026',        'RENDA_FIXA', 1,    NULL,      180000.00, current_date + 9),
    (6, NULL, 'TESOURO-SELIC-2029', 'RENDA_FIXA', 20,   NULL,      290400.00, DATE '2029-03-01');

-- ---------------------------------------------------------------- notícias
-- Manchetes fictícias, só para exercitar o motor de sentimento.
INSERT INTO news_articles (id, source, url, headline, published_at) VALUES
    (1, 'Seed', 'https://exemplo.com/noticias/1', 'Petroleira supera expectativa de produção no trimestre (exemplo)', now() - interval '3 hours'),
    (2, 'Seed', 'https://exemplo.com/noticias/2', 'Bancos recuam com discussão sobre nova regra de provisões (exemplo)', now() - interval '5 hours'),
    (3, 'Seed', 'https://exemplo.com/noticias/3', 'Minério de ferro cai com demanda fraca na China (exemplo)', now() - interval '8 hours');

INSERT INTO news_mentions (news_id, ticker, sentiment) VALUES
    (1, 'PETR4',  0.70),
    (2, 'ITUB4', -0.60),
    (2, 'BBAS3', -0.40),
    (2, 'BANCOS', -0.50),
    (3, 'VALE3', -0.55);

-- ---------------------------------------------------------------- agenda
-- Seg–sex, 9h–12h e 14h–18h
INSERT INTO advisor_availability (advisor_id, weekday, start_time, end_time)
SELECT 1, d, t.s, t.e
FROM generate_series(1, 5) AS d,
     (VALUES (TIME '09:00', TIME '12:00'), (TIME '14:00', TIME '18:00')) AS t(s, e);

INSERT INTO meetings (advisor_id, client_id, starts_at, ends_at, topic, status, created_via, initiated_by) VALUES
    -- Pedida pelo assessor e já confirmada pela cliente.
    (1, 5,
     ((current_date + 3) + TIME '10:00') AT TIME ZONE 'America/Sao_Paulo',
     ((current_date + 3) + TIME '10:30') AT TIME ZONE 'America/Sao_Paulo',
     'Revisão de fundos imobiliários', 'CONFIRMED', 'ADVISOR', 'ADVISOR'),
    -- Pedida pelo cliente; aguarda a confirmação da assessora.
    (1, 3,
     ((current_date + 1) + TIME '14:00') AT TIME ZONE 'America/Sao_Paulo',
     ((current_date + 1) + TIME '14:30') AT TIME ZONE 'America/Sao_Paulo',
     'Pedido de aporte em cripto', 'PENDING', 'CHAT', 'CLIENT'),
    -- Pedida pela assessora; aguarda a confirmação da cliente.
    (1, 6,
     ((current_date + 2) + TIME '11:00') AT TIME ZONE 'America/Sao_Paulo',
     ((current_date + 2) + TIME '11:30') AT TIME ZONE 'America/Sao_Paulo',
     'Alternativa ao CDB que vence', 'PENDING', 'ADVISOR', 'ADVISOR');

-- ---------------------------------------------------------------- copiloto
-- Rafael pediu um aporte por voz; o Gemini chamou update_portfolio.
INSERT INTO chat_messages (id, client_id, role, content, input_mode, tool_calls, created_at) VALUES
    (1, 3, 'USER', 'Quero colocar mais uns 50 mil em cripto esse mês', 'VOICE', '[]', now() - interval '2 hours'),
    (2, 3, 'ASSISTANT', 'Anotei seu pedido de aporte de R$ 50 mil em cripto e avisei sua assessora.', 'TEXT',
     '[{"name": "update_portfolio", "arguments": {"client_id": 3, "request_type": "APORTE", "asset_class": "CRIPTO", "amount": 50000}}]',
     now() - interval '2 hours' + interval '3 seconds');

INSERT INTO portfolio_requests (id, client_id, request_type, details, status, source, chat_message_id, created_at) VALUES
    (1, 3, 'APORTE', '{"asset_class": "CRIPTO", "amount": 50000}', 'PENDING', 'CHAT', 1, now() - interval '2 hours');

INSERT INTO notifications (user_id, kind, title, body, payload, created_at) VALUES
    (1, 'PORTFOLIO_REQUEST', 'Rafael Monteiro pediu um aporte',
     'Aporte de R$ 50 mil em cripto, pedido pelo copiloto de voz.',
     '{"client_id": 3, "request_id": 1}', now() - interval '2 hours');

-- ---------------------------------------------------------------- sequências
-- Como os ids acima foram explícitos, avança as sequências de identidade.
SELECT setval(pg_get_serial_sequence('users', 'id'),                 (SELECT max(id) FROM users));
SELECT setval(pg_get_serial_sequence('open_finance_consents', 'id'), (SELECT max(id) FROM open_finance_consents));
SELECT setval(pg_get_serial_sequence('external_accounts', 'id'),     (SELECT max(id) FROM external_accounts));
SELECT setval(pg_get_serial_sequence('news_articles', 'id'),         (SELECT max(id) FROM news_articles));
SELECT setval(pg_get_serial_sequence('chat_messages', 'id'),         (SELECT max(id) FROM chat_messages));
SELECT setval(pg_get_serial_sequence('portfolio_requests', 'id'),    (SELECT max(id) FROM portfolio_requests));

COMMIT;
