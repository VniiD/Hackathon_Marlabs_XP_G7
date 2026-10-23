from fastapi import APIRouter, Depends, HTTPException

from src.modules.market_intelligence.models import CurrencyRate, NewsItem, Quote
from src.modules.market_intelligence.services import (
    MarketIntelligenceService,
    get_market_service,
)

router = APIRouter(prefix="/market", tags=["market_intelligence"])


@router.get("/news", response_model=list[NewsItem])
async def get_news(
    svc: MarketIntelligenceService = Depends(get_market_service),
) -> list[NewsItem]:
    try:
        return await svc.fetch_news()
    except Exception as exc:  # pragma: no cover - proteção de integração externa
        raise HTTPException(
            502, f"Não foi possível carregar o feed de notícias: {exc}"
        ) from exc


@router.get("/currency-line", response_model=list[CurrencyRate])
async def get_currency_line(
    svc: MarketIntelligenceService = Depends(get_market_service),
) -> list[CurrencyRate]:
    try:
        return await svc.fetch_currency_line()
    except Exception as exc:  # pragma: no cover - proteção de integração externa
        raise HTTPException(
            502, f"Não foi possível carregar a linha de câmbio: {exc}"
        ) from exc


@router.get("/quotes/{ticker}", response_model=Quote)
def get_quote(
    ticker: str, svc: MarketIntelligenceService = Depends(get_market_service)
) -> Quote:
    quote = svc.get_quote(ticker.upper())
    if quote is None:
        raise HTTPException(404, "Cotação indisponível")
    return quote
