from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.core.exceptions import ConflictError, DomainError, ForbiddenError, NotFoundError
from src.modules.scheduling.models import (
    Meeting,
    MeetingConfirm,
    MeetingParty,
    MeetingRequest,
    MeetingStatus,
    TimeSlot,
)

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
_SLOT_MINUTES = 30
_WORKDAY_START = time(9, 0, tzinfo=LOCAL_TZ)
_WORKDAY_END = time(18, 0, tzinfo=LOCAL_TZ)


class SchedulingService:
    def __init__(self) -> None:
        self._meetings: list[Meeting] = []

    def list_meetings_for_advisor(self, advisor_id: int) -> list[Meeting]:
        return sorted((m for m in self._meetings if m.advisor_id == advisor_id), key=lambda m: m.slot.start)

    def list_for_advisor(self, advisor_id: int) -> list[Meeting]:
        return self.list_meetings_for_advisor(advisor_id)

    def list_meetings_for_client(self, client_id: int) -> list[Meeting]:
        return sorted((m for m in self._meetings if m.client_id == client_id), key=lambda m: m.slot.start)

    def list_for_client(self, client_id: int) -> list[Meeting]:
        return self.list_meetings_for_client(client_id)

    def get(self, meeting_id: int) -> Meeting:
        for meeting in self._meetings:
            if meeting.id == meeting_id:
                return meeting
        raise NotFoundError(f"Reunião {meeting_id} não encontrada")

    def _has_overlap(self, advisor_id: int, slot: TimeSlot) -> bool:
        for meeting in self.list_meetings_for_advisor(advisor_id):
            if meeting.status == MeetingStatus.CANCELLED:
                continue
            if slot.start < meeting.slot.end and meeting.slot.start < slot.end:
                return True
        return False

    def find_free_slots(self, advisor_id: int, limit: int = 6, now: datetime | None = None) -> list[TimeSlot]:
        anchor = (now or datetime.now(LOCAL_TZ)).astimezone(LOCAL_TZ)
        slots: list[TimeSlot] = []
        days_checked = 0

        while len(slots) < limit and days_checked < 30:
            candidate_day = anchor.date() + timedelta(days=days_checked)
            if candidate_day.weekday() < 5:
                windows = [
                    (time(9, 0, tzinfo=LOCAL_TZ), time(12, 0, tzinfo=LOCAL_TZ)),
                    (time(14, 0, tzinfo=LOCAL_TZ), time(18, 0, tzinfo=LOCAL_TZ)),
                ]
                for window_start, window_end in windows:
                    current = datetime.combine(candidate_day, window_start)
                    stop = datetime.combine(candidate_day, window_end)
                    while current + timedelta(minutes=_SLOT_MINUTES) <= stop:
                        slot = TimeSlot(start=current, end=current + timedelta(minutes=_SLOT_MINUTES))
                        if candidate_day == anchor.date() and slot.start < anchor:
                            current += timedelta(minutes=_SLOT_MINUTES)
                            continue
                        if not self._has_overlap(advisor_id, slot):
                            slots.append(slot)
                            if len(slots) >= limit:
                                return slots
                        current += timedelta(minutes=_SLOT_MINUTES)
            days_checked += 1
        return slots

    def schedule(self, req: MeetingRequest) -> Meeting:
        slot = req.preferred or next(iter(self.find_free_slots(req.advisor_id, limit=1)), None)
        if slot is None:
            raise DomainError("Sem horários livres")
        if self._has_overlap(req.advisor_id, slot):
            raise ConflictError("Horário indisponível para o assessor")

        meeting = Meeting(
            id=(max((m.id for m in self._meetings), default=0) + 1),
            client_id=req.client_id,
            advisor_id=req.advisor_id,
            slot=slot,
            topic=req.topic,
            initiated_by=req.initiated_by,
            context=req.context,
        )
        self._meetings.append(meeting)
        return meeting

    def confirm(self, meeting_id: int, user_id: int, role: MeetingParty) -> Meeting:
        meeting = self.get(meeting_id)
        if meeting.status == MeetingStatus.CONFIRMED:
            raise ConflictError("Reunião já confirmada")

        expected_party = MeetingParty.CLIENT if meeting.initiated_by == MeetingParty.ADVISOR else MeetingParty.ADVISOR
        expected_user_id = meeting.client_id if expected_party == MeetingParty.CLIENT else meeting.advisor_id

        if role != expected_party or user_id != expected_user_id:
            raise ForbiddenError("A confirmação deve ser feita pela parte contrária")

        meeting.status = MeetingStatus.CONFIRMED
        return meeting


_service = SchedulingService()


def get_scheduling_service() -> SchedulingService:
    return _service
