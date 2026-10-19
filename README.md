# Hackathon XP G7 — Plataforma Inteligente para Assessores Financeiros

Monolito modular em Python (FastAPI) com PostgreSQL, Redis e OpenAI (chat do copiloto).

## Estrutura

```
src/
  main.py                      # app FastAPI + routers (/api/v1)
  core/                        # config, banco, Redis, exceções
  modules/
    accounts/                  # usuários, perfis de risco, contexto pessoal
    portfolio/                 # carteira + OpenFinanceIntegrationService
    market_intelligence/       # cotações (Redis pub/sub), notícias, sentimento
    copilot_chat/              # OpenAI (Chat Completions) + Function Calling
    advisor_dashboard/         # DailyAdvisorEngine, Next Best Action
    scheduling/                # agenda e marcação de reuniões
```

Cada módulo expõe `router.py` (HTTP), `models.py` (Pydantic) e `services.py` (regras, injetadas via `Depends`).
Módulos conversam entre si apenas pelos `services`, nunca pelos internos.

## Rodando com Docker Compose

```bash
cp .env.example .env        # preencha OPENAI_API_KEY
docker compose up --build
```

- API: http://localhost:8000 (docs em `/docs`)
- PostgreSQL: `localhost:5432` | Redis: `localhost:6379`

## Rodando localmente (API fora do Docker)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d db redis
uvicorn src.main:app --reload
pytest
```

Fora do Docker, ajuste `DATABASE_URL`/`REDIS_URL` no `.env` para `localhost`.

## Interface web (`web/`)

React + Vite + TypeScript. Por padrão usa dados simulados, então roda sem o backend:

```bash
cd web
npm install
npm run dev                 # http://localhost:5173
```

Para usar o FastAPI no lugar dos mocks, suba o backend na porta 8000 e crie `web/.env` com:

```
VITE_USE_MOCKS=false
```

O Vite encaminha `/api` para `http://localhost:8000`, então não é preciso configurar CORS em dev.

`VITE_USE_MOCKS` tem três modos:

| Valor | O que usa |
|---|---|
| `true` (padrão) | tudo simulado, sem backend |
| `partial` | **agenda, chat e briefing do assessor** vão ao FastAPI (o chat usa a OpenAI e exige `OPENAI_API_KEY`); o resto segue simulado |
| `false` | tudo no FastAPI (várias telas ainda não têm rota, veja abaixo) |

No modo `partial` a API sobe com carteiras e três reuniões de demonstração para os clientes do Postgres
(`src/seed.py`, desligue com `SEED_DEMO_DATA=false`); ela guarda tudo em memória e reiniciar o container zera;
o horário pedido por um lado só vale depois que o outro confirma, e conflito de horário volta 409.

A entrada é uma tela "Quem está acessando?" com perfis prontos: escolha a assessora para ver o painel
do assessor, ou um cliente para ver a carteira. A cliente marcada como "Primeiro acesso" passa antes
pela análise de perfil. Recarregar a página volta os dados simulados ao estado inicial.

A UI só fala com o backend pela interface `Api` em `web/src/api/types.ts`, que tem duas
implementações: `mock.ts` (dados simulados) e `http.ts` (chamadas aos endpoints de `/api/v1`).
Os tipos desse arquivo espelham os `models.py` de cada módulo; ao mudar um modelo Pydantic, atualize o tipo.
As rotas marcadas como "pendente" em `http.ts` (perfis, notícias, pedidos e análise de perfil)
ainda não existem no FastAPI, então por enquanto essas telas só funcionam com os mocks.

Usuários, análise de perfil e anotações do assessor são a exceção: mesmo com os mocks ligados eles vêm do backend.

- **Usuários**: a tela de entrada lista os usuários do Postgres (`GET /api/v1/accounts/profiles`) e
  "Criar conta" grava um cliente novo (`POST /api/v1/accounts/signup`). O navegador lembra quem entrou
  e em qual tela estava, então o F5 não desloga. Sem backend, a entrada cai nos usuários simulados.
- **Análise de perfil**: as respostas ficam em `suitability_answers` (tabela criada pela API no
  primeiro uso) e o perfil calculado atualiza `client_profiles.risk_profile`.
- **Anotações do assessor**: ficam em `advisor_notes` (tabela criada pela API no primeiro uso, já
  com o antigo contexto fixo de hobbies, time e datas convertido em anotações).
- **Áudio**: transcrito pela AssemblyAI (`POST /api/v1/copilot/transcribe`); defina
  `ASSEMBLYAI_API_KEY` no `.env` da raiz. Sem a chave, o cliente ainda pode escrever.

Carteira, prioridades, notícias e pedidos continuam simulados e voltam ao estado inicial no F5.

O banco precisa do schema e do seed de `db/`. Em um volume novo o `docker compose up` aplica os dois
sozinho. Se o seu volume `pgdata` é antigo (sem a tabela `users`), aplique à mão:

```bash
docker compose exec -T db psql -U postgres -d advisor < db/01_schema.sql
docker compose exec -T db psql -U postgres -d advisor < db/02_seed.sql
```

Se a porta 5432 já estiver em uso na sua máquina, defina `DB_PORT` no `.env` (ex.: `DB_PORT=5434`).

Decisões de interface estão em `web/DESIGN.md`.

## Agenda e confirmação de reuniões

Assessor e cliente têm a aba **Agenda** (e o painel/carteira mostram o mesmo componente). Toda reunião
nasce `PENDING` com o campo `initiated_by` (`CLIENT` ou `ADVISOR`) e só vira `CONFIRMED` quando a
**outra** parte confirma; quem pediu vê "Aguardando <nome>", sem botão.

Rotas em `/api/v1/scheduling`:

| Rota | O que faz |
|---|---|
| `GET /advisors/{id}/meetings` · `GET /clients/{id}/meetings` | agenda de cada lado, em ordem de horário |
| `GET /advisors/{id}/free-slots?limit=6` | horários livres: janelas de atendimento (seg-sex, 9h-12h e 14h-18h) menos as reuniões |
| `POST /meetings` | pede reunião (`initiated_by`); 409 se o assessor já tem reunião nesse horário |
| `POST /meetings/{id}/confirm` | corpo `{user_id, role}`; 403 se for quem pediu ou um terceiro, 409 se não estiver pendente |

Ainda não há login, então quem confirma vem no corpo da requisição (o `role` evita confundir ids iguais
de assessor e cliente). Com autenticação, trocar por usuário do token. Testes: `pytest tests/test_scheduling.py`.

## Chat com o copiloto e contexto da reunião

`POST /api/v1/copilot/chat` conversa com a OpenAI (`OPENAI_MODEL`, padrão `gpt-4o-mini`) usando function
calling. O histórico fica no servidor por cliente (`GET /copilot/chat/{client_id}/history`). Ferramentas:
`get_portfolio_summary`, `get_relevant_news`, `get_free_slots`, `save_meeting_context` e `schedule_meeting`.

**Reunião só sai com contexto.** `schedule_meeting` recusa (`missing_context`) até o cliente responder, no
chat, a quatro perguntas (assunto, expectativa, prazo e mudanças recentes). A regra é do servidor, não só do
prompt. Ao marcar, as respostas viram `Meeting.context` e o cliente não consegue marcar pela tela de
carteira: o botão leva ao chat. Sem `OPENAI_API_KEY` o chat responde 502.

**O que o assessor vê.** `GET /api/v1/advisor/{advisor_id}/meetings/{meeting_id}/briefing` junta o contexto
do chat, a carteira (total, alocação, maiores posições), as notícias que citam ativos do cliente
(`GET /market/news`, hoje dados de demonstração) e pontos de conversa gerados pelo LLM, com um fallback por
regras se a OpenAI falhar. Aparece como "Preparação da reunião" no detalhe do cliente. Testes:
`pytest tests/test_copilot_chat.py` (o LLM é um fake; nenhum teste chama a OpenAI).

## Estado atual

Esqueleto: `accounts` e `scheduling` usam memória (a agenda já tem regras e testes; falta persistir); `portfolio` (Open Finance), `market_intelligence` (cotações) são stubs com TODOs. Migrações: `alembic init` pendente (pasta `alembic/` reservada).
