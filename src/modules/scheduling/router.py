from fastapi import APIRouter, Depends

from src.modules.scheduling.models import (
    Meeting,
    MeetingConfirm,
    MeetingRequest,
    TimeSlot,
)
from src.modules.scheduling.services import SchedulingService, get_scheduling_service

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


@router.get("/advisors/{advisor_id}/meetings", response_model=list[Meeting])
def list_meetings(
    advisor_id: int, svc: SchedulingService = Depends(get_scheduling_service)
) -> list[Meeting]:
    return svc.list_meetings_for_advisor(advisor_id)


@router.get("/clients/{client_id}/meetings", response_model=list[Meeting])
def list_client_meetings(
    client_id: int, svc: SchedulingService = Depends(get_scheduling_service)
) -> list[Meeting]:
    return svc.list_meetings_for_client(client_id)


@router.get("/meetings/{meeting_id}", response_model=Meeting)
def get_meeting(
    meeting_id: int, svc: SchedulingService = Depends(get_scheduling_service)
) -> Meeting:
    return svc.get(meeting_id)


@router.get("/advisors/{advisor_id}/free-slots", response_model=list[TimeSlot])
def available_slots(
    advisor_id: int, svc: SchedulingService = Depends(get_scheduling_service)
) -> list[TimeSlot]:
    return svc.find_free_slots(advisor_id, limit=6)


@router.post("/meetings", response_model=Meeting, status_code=201)
def schedule_meeting(
    req: MeetingRequest, svc: SchedulingService = Depends(get_scheduling_service)
) -> Meeting:
    return svc.schedule(req)


@router.post("/meetings/{meeting_id}/confirm", response_model=Meeting)
def confirm_meeting(
    meeting_id: int,
    payload: MeetingConfirm,
    svc: SchedulingService = Depends(get_scheduling_service),
) -> Meeting:
    return svc.confirm(meeting_id, payload.user_id, payload.role)
