# CLAUDE.md

Plataforma web para assessores financeiros e seus clientes (Hackathon XP, grupo 7). O assessor vê quem
precisa de atenção hoje e o patrimônio consolidado da carteira; o cliente vê a própria carteira,
conversa com um copilot e marca reuniões. O texto de produto e as telas estão em português.

## Stack e arquitetura

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Redis, OpenAI (chat/Function Calling).
- **Monolito modular** em `src/`. Cada módulo de `src/modules/` tem `models.py` (Pydantic, é o contrato da
  API), `services.py` (regras; injetado com `Depends`) e `router.py` (HTTP, prefixo `/api/v1`). Alguns também
  têm `orm.py` (tabelas SQLAlchemy). Módulos conversam só pelos `services` uns dos outros.
- **Módulos:** `accounts` (usuários, perfil de risco CONSERVADOR/MODERADO/ARROJADO, contexto pessoal),
  `portfolio` (carteira + `OpenFinanceIntegrationService`), `market_intelligence` (cotações/notícias),
  `copilot_chat` (OpenAI via `llm.py`; `tools.py` com as ações; `store.py` com histórico e contexto coletado), `advisor_dashboard` (`DailyAdvisorEngine`, score de
  criticidade e "Próxima Melhor Ação"), `scheduling` (agenda e reuniões). `src/core/` tem config, banco,
  cliente Redis e exceções (`DomainError` vira JSON `{"detail": ...}` com o status da subclasse).
- **Front:** `web/`, React 18 + Vite + TypeScript. Toda a UI fala com os dados pela interface `Api` em
  `web/src/api/types.ts`, com duas implementações: `mock.ts` (dados simulados) e `http.ts` (FastAPI).
  Os tipos de `types.ts` espelham os `models.py`; mudou um modelo Pydantic, atualize o tipo.

## Comandos

```bash
# Backend (raiz do repo; venv em .venv)
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000     # docs em /docs
pytest tests                                   # use "tests" (não a raiz) para não pegar lixo em outras pastas

# Front
cd web && npm install && npm run dev           # http://localhost:5173
npm run build                                  # tsc --noEmit + vite build (checagem de tipos)

# Infra
docker compose up --build                      # api + PostgreSQL 16 + Redis
```

Front: `VITE_USE_MOCKS` = `true` (padrão, tudo simulado), `partial` (agenda, chat e briefing vão ao FastAPI) ou `false`
(tudo no FastAPI; várias telas ainda não têm rota). O Vite faz proxy de `/api` para `VITE_API_PROXY_TARGET`
(padrão `http://localhost:8000`), então não há CORS em dev.

## Estado atual (conferir antes de assumir)

- **Banco, duas trilhas ainda não reconciliadas:** `db/01_schema.sql` + `02_seed.sql` (PostgreSQL, alinhados
  aos `models.py`, carregados pelo `docker-compose` na primeira subida) e `db/schema.sql` + `seed.sql` +
  `init_db.py` + `app.db` (SQLite, tabelas em português: `cliente`, `carteira`, `ativo`, `posicao`...).
  Só `advisor_dashboard/orm.py` e `accounts/orm.py` etc. mapeiam tabelas; **a maioria dos services ainda usa
  armazenamento em memória ou devolve vazio**. Alembic: pasta `alembic/` reservada, sem `init`.
- `scheduling` já está implementado em memória (horários livres, conflito → 409, confirmação dos dois lados).
- `copilot_chat` já conversa com a OpenAI (`OPENAI_API_KEY`). Para marcar reunião o cliente precisa responder 4
  perguntas no chat (`INTAKE_QUESTIONS` em `tools.py`); a tool `schedule_meeting` recusa sem elas e o contexto
  vai em `Meeting.context`. O assessor lê isso em `GET /advisor/{id}/meetings/{id}/briefing` (contexto + carteira
  + notícias + pontos de conversa). Histórico e contexto ficam em memória, perdem-se ao reiniciar.
- `portfolio` (Open Finance) e `market_intelligence` (cotações) são stubs com TODO; carteiras e notícias vêm de
  dados de demonstração em memória (`src/seed.py`, chamado no `lifespan`; `SEED_DEMO_DATA=false` desliga). Os
  clientes vêm do Postgres (`db/02_seed.sql`, ids 2–6) e o seed casa as carteiras pelo nome; sem o banco
  carregado, o chat devolve 404. Se o volume do Postgres já existia antes do schema, o `initdb` não roda de
  novo: aplique `db/01_schema.sql` e `db/02_seed.sql` com `psql` ou recrie o volume.
- O motor do dashboard recebe sinais vazios: score 0 para todos com o backend real. Falta alimentá-lo com
  variação de carteira e gatilhos de relacionamento.
- Não há login: a tela "Quem está acessando?" escolhe o perfil (`LoginProfile`, assessora id 1 ou um cliente). PyJWT está nas dependências.
- A tela "Visão geral" do consultor (patrimônio agregado por classe e clientes por perfil) é servida por
  `GET /advisor/{id}/overview`, montada em `advisor_dashboard/overview.py`. `src/seed.py` popula os stores em
  memória na subida da API (ver `copilot_chat` acima). Há correção de cotação sem Redis guardada em `git stash`
  (GitHub Desktop).

## Armadilhas

- **Porta 8000 pode estar ocupada** no Windows por uma regra `netsh portproxy` (serviço IP Helper). Remover
  exige admin: `netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0`. Alternativa:
  subir o backend em outra porta e ajustar `VITE_API_PROXY_TARGET`.
- **Redis fora do ar:** `get_redis()` não tem fallback; cada chamada a `market/quotes/{ticker}` falha. A tela
  de detalhe do cliente pede uma cotação por ativo, então proteja a chamada no front ou degrade no serviço.
- SQLite liga chave estrangeira só com `PRAGMA foreign_keys = ON` em cada conexão. Mude o banco editando os
  `.sql` e rodando `python db/init_db.py`, nunca o `app.db` direto (binário: conflito de merge se resolve nos `.sql`).
- Dois Vite ao mesmo tempo disputam `web/node_modules/.vite`; suba um de cada vez.
- Valores `Decimal` do Pydantic chegam como string no JSON; datas em ISO 8601.

## Convenções

- Código e identificadores em inglês; textos de interface, mensagens de erro e docs em português.
- Tipagem estrita: Pydantic nas bordas, `strict` no TypeScript. Dinheiro é `Decimal`, nunca `float`.
- Dependências entre serviços via `Depends(get_*_service)`; sem estado global novo fora dos stubs existentes.
- Mudou rota ou modelo: atualize `web/src/api/{types,http,mock}.ts` e o README.
