from fastapi import APIRouter, Depends, Response, status

from src.modules.accounts.models import (
    ClientCreate,
    ClientProfile,
    AdvisorNote,
    AdvisorNoteText,
    LoginProfile,
    SignUpRequest,
    Suitability,
    SuitabilityAnswer,
)
from src.modules.accounts.services import AccountsService, get_accounts_service
from src.modules.accounts.notes import NotesService, get_notes_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/profiles", response_model=list[LoginProfile])
def list_profiles(
    svc: AccountsService = Depends(get_accounts_service),
) -> list[LoginProfile]:
    return svc.list_profiles()


@router.post("/signup", response_model=LoginProfile)
def sign_up(
    data: SignUpRequest, svc: AccountsService = Depends(get_accounts_service)
) -> LoginProfile:
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


@router.get(
    "/advisors/{advisor_id}/clients/{client_id}/notes",
    response_model=list[AdvisorNote],
)
def list_client_notes(
    advisor_id: int,
    client_id: int,
    svc: NotesService = Depends(get_notes_service),
) -> list[AdvisorNote]:
    return svc.list_for_client(client_id, advisor_id)


@router.post(
    "/advisors/{advisor_id}/clients/{client_id}/notes",
    response_model=AdvisorNote,
    status_code=status.HTTP_201_CREATED,
)
def add_client_note(
    advisor_id: int,
    client_id: int,
    data: AdvisorNoteText,
    svc: NotesService = Depends(get_notes_service),
) -> AdvisorNote:
    return svc.add(client_id, advisor_id, data.text)


@router.patch("/advisors/{advisor_id}/notes/{note_id}", response_model=AdvisorNote)
def edit_client_note(
    advisor_id: int,
    note_id: int,
    data: AdvisorNoteText,
    svc: NotesService = Depends(get_notes_service),
) -> AdvisorNote:
    return svc.edit(note_id, advisor_id, data.text)


@router.delete(
    "/advisors/{advisor_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_client_note(
    advisor_id: int,
    note_id: int,
    svc: NotesService = Depends(get_notes_service),
) -> Response:
    svc.delete(note_id, advisor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
