from fastapi import APIRouter, Depends

from src.modules.portfolio.models import (
    ChangeRequest,
    ChangeRequestCreate,
    UnifiedPortfolio,
)
from src.modules.portfolio.services import PortfolioService, get_portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/{client_id}", response_model=UnifiedPortfolio)
def get_portfolio(
    client_id: int, svc: PortfolioService = Depends(get_portfolio_service)
) -> UnifiedPortfolio:
    return svc.get_unified_portfolio(client_id)


@router.post(
    "/{client_id}/change-requests", response_model=ChangeRequest, status_code=201
)
def create_change_request(
    client_id: int,
    req: ChangeRequestCreate,
    svc: PortfolioService = Depends(get_portfolio_service),
) -> ChangeRequest:
    if req.client_id != client_id:
        req = ChangeRequestCreate(
            client_id=client_id, kind=req.kind, message=req.message
        )
    return svc.create_change_request(req)
