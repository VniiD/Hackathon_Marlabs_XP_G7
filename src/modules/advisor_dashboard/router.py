from fastapi import APIRouter, Depends

from src.modules.advisor_dashboard.models import (
    AdvisorOverview,
    NewsImpact,
    PrioritizedClient,
)
from src.modules.advisor_dashboard.services import (
    AdvisorDashboardService,
    MeetingBriefing,
    get_dashboard_service,
)
from src.modules.portfolio.models import ChangeRequest

router = APIRouter(prefix="/advisor", tags=["advisor_dashboard"])


@router.get("/{advisor_id}/overview", response_model=AdvisorOverview)
def advisor_overview(
    advisor_id: int, svc: AdvisorDashboardService = Depends(get_dashboard_service)
) -> AdvisorOverview:
    return svc.overview(advisor_id)


@router.get("/{advisor_id}/priorities", response_model=list[PrioritizedClient])
def daily_priorities(
    advisor_id: int, svc: AdvisorDashboardService = Depends(get_dashboard_service)
) -> list[PrioritizedClient]:
    return svc.daily_priority_list(advisor_id)


@router.get("/{advisor_id}/news-impact", response_model=list[NewsImpact])
def advisor_news_impact(
    advisor_id: int, svc: AdvisorDashboardService = Depends(get_dashboard_service)
) -> list[NewsImpact]:
    return svc.news_impact_list(advisor_id)


@router.get("/{advisor_id}/change-requests", response_model=list[ChangeRequest])
def advisor_change_requests(
    advisor_id: int, svc: AdvisorDashboardService = Depends(get_dashboard_service)
) -> list[ChangeRequest]:
    return svc.change_requests(advisor_id)


@router.get(
    "/{advisor_id}/meetings/{meeting_id}/briefing", response_model=MeetingBriefing
)
def meeting_briefing(
    advisor_id: int,
    meeting_id: int,
    svc: AdvisorDashboardService = Depends(get_dashboard_service),
) -> MeetingBriefing:
    return svc.build_briefing(advisor_id, meeting_id)
