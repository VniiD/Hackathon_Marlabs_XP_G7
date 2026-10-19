import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.exceptions import register_exception_handlers
from src.modules.accounts.router import router as accounts_router
from src.modules.advisor_dashboard.router import router as dashboard_router
from src.modules.copilot_chat.router import router as copilot_router
from src.modules.market_intelligence.router import router as market_router
from src.modules.portfolio.router import router as portfolio_router
from src.modules.scheduling.router import router as scheduling_router
from src.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Carteiras e reuniões ainda vivem em memória: sem isto o backend sobe sem elas. Os clientes
    # vêm do Postgres, então, com o banco fora do ar, a API sobe mesmo assim, só sem a demonstração.
    if get_settings().seed_demo_data:
        try:
            seed_demo_data()
        except Exception:
            logger.warning("Dados de demonstração não carregados (o Postgres está no ar?)", exc_info=True)
    yield


logger = logging.getLogger("uvicorn.error")
app = FastAPI(title="Plataforma Inteligente para Assessores Financeiros", lifespan=lifespan)
register_exception_handlers(app)

for r in (
    accounts_router,
    portfolio_router,
    market_router,
    copilot_router,
    dashboard_router,
    scheduling_router,
):
    app.include_router(r, prefix="/api/v1")


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}
