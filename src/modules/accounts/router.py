from fastapi import APIRouter, Depends

from src.modules.accounts.models import (
    ClientCreate,
    ClientProfile,
    LoginProfile,
    SignUpRequest,
    Suitability,
    SuitabilityAnswer,
)
from src.modules.accounts.services import AccountsService, get_accounts_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/profiles", response_model=list[LoginProfile])
def list_profiles(svc: AccountsService = Depends(get_accounts_service)) -> list[LoginProfile]:
    return svc.list_profiles()


@router.post("/signup", response_model=LoginProfile)
def sign_up(data: SignUpRequest, svc: AccountsService = Depends(get_accounts_service)) -> LoginProfile:
    return svc.sign_up(data.name, data.email)


@router.post("/clients", response_model=ClientProfile, status_code=201)
def create_client(
    data: ClientCreate, svc: AccountsService = Depends(get_accounts_service)
) -> ClientProfile:
    return svc.create_client(data)


@router.get("/clients/{client_id}", response_model=ClientProfile)
def get_client(
    client_id: int, svc: AccountsService = Depends(get_accounts_service)
) -> ClientProfile:
    return svc.get_client(client_id)


@router.get("/clients/{client_id}/suitability", response_model=Suitability)
def get_suitability(
    client_id: int, svc: AccountsService = Depends(get_accounts_service)
) -> Suitability:
    return svc.get_suitability(client_id)


@router.post("/clients/{client_id}/suitability", response_model=Suitability)
def answer_suitability(
    client_id: int,
    answer: SuitabilityAnswer,
    svc: AccountsService = Depends(get_accounts_service),
) -> Suitability:
    return svc.answer_suitability(client_id, answer)
