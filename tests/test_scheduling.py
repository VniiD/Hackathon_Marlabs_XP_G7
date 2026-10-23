from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.main import app
from src.modules.scheduling.models import (
    ContextAnswer,
    MeetingContext,
    MeetingParty,
    MeetingRequest,
    MeetingStatus,
    TimeSlot,
)
from src.modules.scheduling.services import (
    LOCAL_TZ,
    SchedulingService,
    get_scheduling_service,
)

ADVISOR, CLIENT = 1, 10
# Segunda-feira ao meio-dia; os próximos horários livres são 14h do mesmo dia.
MONDAY_NOON = datetime(2030, 1, 7, 12, 0, tzinfo=LOCAL_TZ)


def _slot(day_offset: int, hour: int) -> TimeSlot:
    start = (datetime.now(LOCAL_TZ) + timedelta(days=day_offset)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return TimeSlot(start=start, end=start + timedelta(minutes=30))


def _request(
    initiated_by: MeetingParty, slot: TimeSlot | None = None
) -> MeetingRequest:
    return MeetingRequest(
        client_id=CLIENT,
        advisor_id=ADVISOR,
        preferred=slot or _slot(2, 10),
        initiated_by=initiated_by,
    )


def test_free_slots_follow_working_windows():
    svc = SchedulingService()
    slots = svc.find_free_slots(ADVISOR, limit=4, now=MONDAY_NOON)
    assert [s.start.hour for s in slots] == [14, 14, 15, 15]
    assert [s.start.minute for s in slots] == [0, 30, 0, 30]


def test_free_slots_skip_weekend():
    svc = SchedulingService()
    friday_evening = datetime(2030, 1, 11, 17, 45, tzinfo=LOCAL_TZ)
    slots = svc.find_free_slots(ADVISOR, limit=1, now=friday_evening)
    assert slots[0].start.date().isoformat() == "2030-01-14"  # segunda
    assert slots[0].start.hour == 9


def test_booked_slot_is_no_longer_free():
    svc = SchedulingService()
    free = svc.find_free_slots(ADVISOR, limit=1)[0]
    svc.schedule(MeetingRequest(client_id=CLIENT, advisor_id=ADVISOR, preferred=free))
    assert free.start not in [s.start for s in svc.find_free_slots(ADVISOR)]


def test_schedule_without_preferred_takes_first_free_slot():
    svc = SchedulingService()
    expected = svc.find_free_slots(ADVISOR, limit=1)[0]
    meeting = svc.schedule(MeetingRequest(client_id=CLIENT, advisor_id=ADVISOR))
    assert meeting.slot.start == expected.start
    assert meeting.status == MeetingStatus.PENDING


def test_overlapping_meeting_is_refused():
    svc = SchedulingService()
    slot = _slot(2, 10)
    svc.schedule(_request(MeetingParty.CLIENT, slot))
    overlapping = TimeSlot(
        start=slot.start + timedelta(minutes=15), end=slot.end + timedelta(minutes=15)
    )
    with pytest.raises(ConflictError):
        svc.schedule(_request(MeetingParty.ADVISOR, overlapping))


def test_client_request_is_confirmed_only_by_advisor():
    svc = SchedulingService()
    meeting = svc.schedule(_request(MeetingParty.CLIENT))
    with pytest.raises(ForbiddenError):
        svc.confirm(meeting.id, CLIENT, MeetingParty.CLIENT)  # quem pediu não confirma
    with pytest.raises(ForbiddenError):
        svc.confirm(meeting.id, 999, MeetingParty.ADVISOR)  # terceiros também não
    assert (
        svc.confirm(meeting.id, ADVISOR, MeetingParty.ADVISOR).status
        == MeetingStatus.CONFIRMED
    )


def test_advisor_request_is_confirmed_only_by_client():
    svc = SchedulingService()
    meeting = svc.schedule(_request(MeetingParty.ADVISOR))
    with pytest.raises(ForbiddenError):
        svc.confirm(meeting.id, ADVISOR, MeetingParty.ADVISOR)
    assert (
        svc.confirm(meeting.id, CLIENT, MeetingParty.CLIENT).status
        == MeetingStatus.CONFIRMED
    )


def test_same_id_on_both_sides_cannot_confirm_own_request():
    # Ids de usuário podem coincidir entre assessor e cliente (seed em memória): o papel decide.
    svc = SchedulingService()
    meeting = svc.schedule(
        MeetingRequest(
            client_id=1,
            advisor_id=1,
            preferred=_slot(2, 10),
            initiated_by=MeetingParty.ADVISOR,
        )
    )
    with pytest.raises(ForbiddenError):
        svc.confirm(meeting.id, 1, MeetingParty.ADVISOR)
    assert (
        svc.confirm(meeting.id, 1, MeetingParty.CLIENT).status
        == MeetingStatus.CONFIRMED
    )


def test_confirm_twice_and_unknown_meeting():
    svc = SchedulingService()
    meeting = svc.schedule(_request(MeetingParty.CLIENT))
    svc.confirm(meeting.id, ADVISOR, MeetingParty.ADVISOR)
    with pytest.raises(ConflictError):
        svc.confirm(meeting.id, ADVISOR, MeetingParty.ADVISOR)
    with pytest.raises(NotFoundError):
        svc.confirm(404, ADVISOR, MeetingParty.ADVISOR)


def test_http_flow():
    svc = SchedulingService()
    app.dependency_overrides[get_scheduling_service] = lambda: svc
    try:
        http = TestClient(app)
        free = http.get(f"/api/v1/scheduling/advisors/{ADVISOR}/free-slots").json()
        assert len(free) == 6

        body = {
            "client_id": CLIENT,
            "advisor_id": ADVISOR,
            "preferred": free[0],
            "initiated_by": "ADVISOR",
        }
        created = http.post("/api/v1/scheduling/meetings", json=body)
        assert created.status_code == 201
        meeting = created.json()
        assert meeting["status"] == "PENDING" and meeting["initiated_by"] == "ADVISOR"

        assert (
            http.post("/api/v1/scheduling/meetings", json=body).status_code == 409
        )  # mesmo horário

        confirm = f"/api/v1/scheduling/meetings/{meeting['id']}/confirm"
        assert (
            http.post(confirm, json={"user_id": ADVISOR, "role": "ADVISOR"}).status_code
            == 403
        )
        done = http.post(confirm, json={"user_id": CLIENT, "role": "CLIENT"})
        assert done.status_code == 200 and done.json()["status"] == "CONFIRMED"

        assert (
            http.get(f"/api/v1/scheduling/advisors/{ADVISOR}/meetings").json()[0]["id"]
            == meeting["id"]
        )
        assert (
            http.get(f"/api/v1/scheduling/clients/{CLIENT}/meetings").json()[0]["id"]
            == meeting["id"]
        )
        assert http.get("/api/v1/scheduling/clients/77/meetings").json() == []
    finally:
        app.dependency_overrides.clear()


def test_meeting_keeps_context_and_can_be_fetched():
    svc = SchedulingService()
    context = MeetingContext(
        answers=[
            ContextAnswer(
                key="motivo", question="Qual o assunto?", answer="CDB vencendo"
            )
        ],
        summary="Assunto: CDB vencendo",
    )
    req = _request(MeetingParty.CLIENT).model_copy(update={"context": context})
    meeting = svc.schedule(req)
    assert svc.get(meeting.id).context == context
    assert svc.schedule(_request(MeetingParty.ADVISOR, _slot(3, 10))).context is None
    with pytest.raises(NotFoundError):
        svc.get(404)

    app.dependency_overrides[get_scheduling_service] = lambda: svc
    try:
        http = TestClient(app)
        body = http.get(f"/api/v1/scheduling/meetings/{meeting.id}").json()
        assert body["context"]["summary"] == "Assunto: CDB vencendo"
        assert http.get("/api/v1/scheduling/meetings/404").status_code == 404
    finally:
        app.dependency_overrides.clear()
