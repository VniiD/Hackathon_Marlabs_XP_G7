-- =====================================================================
-- schema.sql — estrutura do banco (fonte da verdade)
-- Para aplicar:  python scripts/init_db.py
-- Diagrama:      esquema-assessor-xp.drawio (MVP do hackathon, 10 tabelas)
-- =====================================================================
-- Convenções (seguem o diagrama):
--   * tabelas no singular, snake_case
--   * PK:     id INTEGER PRIMARY KEY AUTOINCREMENT
--   * FK:     id_<tabela> (ex: id_cliente). Quando a FK tem um papel
--             próprio, o nome é o papel (id_emissor, id_custodiante...)
--   * datas:  TEXT 'AAAA-MM-DD', validadas com CHECK (date(x) IS x)
--   * bool:   INTEGER 0/1 com CHECK
--   * enum:   TEXT com CHECK. Siglas em MAIÚSCULAS (PF, BRL, CDI),
--             palavras em minúsculas (email, credito, positivo)
--   * número: NUMERIC(p,s) como no diagrama. O SQLite não força a
--             precisão; o CHECK de typeof barra texto como '1.234,56'
--   * PRAGMA foreign_keys vale só para a conexão atual: ligue também
--     em toda conexão aberta pelo app, senão as FKs não são checadas
-- =====================================================================

PRAGMA foreign_keys = ON;

-- =====================================================================
-- CLIENTE
-- =====================================================================

-- Sem CPF, como no diagrama.
CREATE TABLE cliente (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT    NOT NULL,
    tipo_pessoa  TEXT    NOT NULL CHECK (tipo_pessoa IN ('PF', 'PJ'))
);

-- Um cliente possui uma ou mais carteiras.
CREATE TABLE carteira (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente  INTEGER NOT NULL REFERENCES cliente(id) ON DELETE CASCADE,
    nome        TEXT    NOT NULL
);

CREATE INDEX idx_carteira_cliente ON carteira(id_cliente);

CREATE TABLE contato_cliente (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente    INTEGER NOT NULL REFERENCES cliente(id) ON DELETE CASCADE,
    tipo_contato  TEXT    NOT NULL
                          CHECK (tipo_contato IN ('email', 'telefone', 'whatsapp')),
    valor         TEXT    NOT NULL,
    principal     INTEGER NOT NULL DEFAULT 0 CHECK (principal IN (0, 1))
);

CREATE INDEX idx_contato_cliente_cliente ON contato_cliente(id_cliente);

-- No máximo um contato principal por cliente e tipo.
CREATE UNIQUE INDEX uq_contato_cliente_principal
    ON contato_cliente(id_cliente, tipo_contato) WHERE principal = 1;

-- =====================================================================
-- INSTITUIÇÕES
-- =====================================================================

-- Base da soma do FGC: o limite de garantia é por conglomerado.
CREATE TABLE conglomerado (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT    NOT NULL
);

-- Bancos e empresas: emissores, devedores de risco e custodiantes.
-- Empresa fora de grupo financeiro vira o seu próprio conglomerado.
CREATE TABLE instituicao (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT    NOT NULL,
    -- 14 caracteres sem pontuação; aceita o CNPJ alfanumérico (A-Z)
    cnpj             TEXT    NOT NULL UNIQUE
                             CHECK (length(cnpj) = 14 AND cnpj NOT GLOB '*[^0-9A-Z]*'),
    id_conglomerado  INTEGER NOT NULL REFERENCES conglomerado(id) ON DELETE RESTRICT
);

CREATE INDEX idx_instituicao_conglomerado ON instituicao(id_conglomerado);

-- =====================================================================
-- POSIÇÕES E ATIVOS
-- =====================================================================

-- Catálogo pequeno: CDB, LCA, CRA, debênture, ação...
-- elegivel_fgc: 'sim'            -> coberto (CDB, LCI, LCA, LC...)
--               'nao'            -> crédito sem FGC (LF, debênture, CRI, CRA)
--               'nao_se_aplica'  -> não é crédito bancário (título público, ação, fundo)
CREATE TABLE tipo_produto (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo        TEXT    NOT NULL UNIQUE,   -- ex: 'CDB', 'CRA', 'DEB'
    nome          TEXT    NOT NULL,          -- ex: 'Certificado de Depósito Bancário'
    classe        TEXT    NOT NULL CHECK (classe IN (
                      'renda_fixa', 'renda_variavel', 'fundo', 'previdencia')),
    subclasse     TEXT    NOT NULL CHECK (subclasse IN (
                      -- renda_fixa
                      'bancario', 'credito_privado', 'titulo_publico',
                      -- renda_variavel
                      'acao', 'fii', 'etf', 'bdr',
                      -- fundo
                      'fundo_renda_fixa', 'fundo_multimercado', 'fundo_acoes', 'fundo_cambial',
                      -- previdencia
                      'pgbl', 'vgbl')),
    elegivel_fgc  TEXT    NOT NULL CHECK (elegivel_fgc IN ('sim', 'nao', 'nao_se_aplica'))
);

-- O que o papel é.
--   id_emissor:       quem emitiu
--   id_devedor_risco: de quem é o risco quando difere do emissor
--                     (ex: CRA de securitizadora com risco Raízen)
--   indexador:        'NENHUM' para renda variável e fundos
--                     (manter igual à lista de evento_alvo.indexador)
--   percentual_indexador: em pontos, 110 = 110% do CDI
--   taxa:                 % a.a. em pontos, 6.5 = IPCA + 6,5% ou PRÉ 6,5%
CREATE TABLE ativo (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                  TEXT    NOT NULL,
    id_tipo_produto       INTEGER NOT NULL REFERENCES tipo_produto(id) ON DELETE RESTRICT,
    id_emissor            INTEGER NOT NULL REFERENCES instituicao(id)  ON DELETE RESTRICT,
    id_devedor_risco      INTEGER          REFERENCES instituicao(id)  ON DELETE RESTRICT,
    codigo                TEXT    UNIQUE,   -- ticker ou código B3; opcional
    moeda                 TEXT    NOT NULL DEFAULT 'BRL'
                                  CHECK (moeda IN ('BRL', 'USD', 'EUR')),
    indexador             TEXT    NOT NULL CHECK (indexador IN (
                                  'CDI', 'SELIC', 'IPCA', 'IGPM', 'PRE', 'NENHUM')),
    percentual_indexador  NUMERIC(7,4)
                          CHECK (percentual_indexador IS NULL OR
                                 (typeof(percentual_indexador) IN ('integer', 'real')
                                  AND percentual_indexador > 0)),
    taxa                  NUMERIC(7,4)
                          CHECK (taxa IS NULL OR typeof(taxa) IN ('integer', 'real')),
    data_vencimento       TEXT    CHECK (date(data_vencimento) IS data_vencimento)
);

CREATE INDEX idx_ativo_tipo_produto  ON ativo(id_tipo_produto);
CREATE INDEX idx_ativo_emissor       ON ativo(id_emissor);
CREATE INDEX idx_ativo_devedor_risco ON ativo(id_devedor_risco);
CREATE INDEX idx_ativo_indexador     ON ativo(indexador);

-- Grão: uma linha = uma carteira × um ativo × uma data_referencia.
CREATE TABLE posicao (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_carteira      INTEGER NOT NULL REFERENCES carteira(id)    ON DELETE CASCADE,
    id_ativo         INTEGER NOT NULL REFERENCES ativo(id)       ON DELETE RESTRICT,
    data_referencia  TEXT    NOT NULL CHECK (date(data_referencia) IS data_referencia),
    quantidade       NUMERIC(18,8) NOT NULL
                     CHECK (typeof(quantidade) IN ('integer', 'real') AND quantidade >= 0),
    pu               NUMERIC(18,8) NOT NULL
                     CHECK (typeof(pu) IN ('integer', 'real') AND pu >= 0),
    valor_bruto      NUMERIC(18,2) NOT NULL
                     CHECK (typeof(valor_bruto) IN ('integer', 'real') AND valor_bruto >= 0),
    id_custodiante   INTEGER NOT NULL REFERENCES instituicao(id) ON DELETE RESTRICT,
    UNIQUE (id_carteira, id_ativo, data_referencia)
);

CREATE INDEX idx_posicao_ativo_data  ON posicao(id_ativo, data_referencia);
CREATE INDEX idx_posicao_custodiante ON posicao(id_custodiante);

-- =====================================================================
-- EVENTOS DE MERCADO
-- =====================================================================

-- Um registro por anúncio (ex: RE da Raízen).
-- Vencimento NÃO é evento: sai de ativo.data_vencimento (P2).
-- Evento cancelado muda o status e sai do resultado da P4.
CREATE TABLE evento_mercado (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    data_evento  TEXT    NOT NULL CHECK (date(data_evento) IS data_evento),
    titulo       TEXT    NOT NULL,
    tipo         TEXT    NOT NULL CHECK (tipo IN ('credito', 'macro', 'noticia')),
    status       TEXT    NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'cancelado')),
    fonte_url    TEXT    NOT NULL,
    data_fim     TEXT    CHECK (date(data_fim) IS data_fim),
    CHECK (data_fim IS NULL OR data_fim >= data_evento)
);

CREATE INDEX idx_evento_mercado_data ON evento_mercado(data_evento);

-- Quem o evento atinge. Cada linha tem EXATAMENTE UM alvo: uma
-- instituição, um conglomerado ou um indexador. Um evento com vários
-- alvos tem várias linhas.
-- indexador casa por valor com ativo.indexador (sem FK).
-- Se um cliente aparece por dois caminhos, vale o mais específico:
-- emissor, depois conglomerado, depois indexador.
CREATE TABLE evento_alvo (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_evento        INTEGER NOT NULL REFERENCES evento_mercado(id) ON DELETE CASCADE,
    id_instituicao   INTEGER          REFERENCES instituicao(id)    ON DELETE RESTRICT,
    id_conglomerado  INTEGER          REFERENCES conglomerado(id)   ON DELETE RESTRICT,
    indexador        TEXT    CHECK (indexador IN ('CDI', 'SELIC', 'IPCA', 'IGPM', 'PRE')),
    sentido_impacto  TEXT    NOT NULL
                             CHECK (sentido_impacto IN ('positivo', 'negativo', 'neutro')),
    CHECK ((id_instituicao  IS NOT NULL)
         + (id_conglomerado IS NOT NULL)
         + (indexador       IS NOT NULL) = 1)
);

-- Sem alvo repetido no mesmo evento (linhas com NULL não colidem).
-- Também servem de índice para buscar os alvos de um evento.
CREATE UNIQUE INDEX uq_evento_alvo_instituicao  ON evento_alvo(id_evento, id_instituicao);
CREATE UNIQUE INDEX uq_evento_alvo_conglomerado ON evento_alvo(id_evento, id_conglomerado);
CREATE UNIQUE INDEX uq_evento_alvo_indexador    ON evento_alvo(id_evento, indexador);