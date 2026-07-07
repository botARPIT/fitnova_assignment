"""Analytics API endpoints — thin router.

Validates request parameters, delegates to AnalyticsService,
returns typed response models.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Query, Request

from schemas.analytics import (
    AdvisorAnalyticsOut,
    OrgOverviewOut,
    TeamAnalyticsOut,
)

log = logging.getLogger("fitnova.routers.analytics")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=OrgOverviewOut)
async def get_overview(
    request: Request,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    team_id: str | None = Query(None),
    advisor_id: str | None = Query(None),
):
    service = request.app.state.analytics_service
    return await service.get_org_overview(
        from_date=from_date,
        to_date=to_date,
        team_id=team_id,
        advisor_id=advisor_id,
    )


@router.get("/teams/{team_id}", response_model=TeamAnalyticsOut)
async def get_team_analytics(
    request: Request,
    team_id: str,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
):
    service = request.app.state.analytics_service
    return await service.get_team_analytics(
        team_id=team_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/advisors/{advisor_id}", response_model=AdvisorAnalyticsOut)
async def get_advisor_analytics(
    request: Request,
    advisor_id: str,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
):
    service = request.app.state.analytics_service
    return await service.get_advisor_analytics(
        advisor_id=advisor_id,
        from_date=from_date,
        to_date=to_date,
    )
