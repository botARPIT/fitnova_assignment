"""API endpoints for org hierarchy (teams, advisors).

Thin routers — no business logic, no repository calls.
"""

import logging

from fastapi import APIRouter, Query, Request

from db.analytics_repository import list_teams, list_advisors
from db.connection import get_pool

log = logging.getLogger("fitnova.routers.org")

router = APIRouter(prefix="/api/org", tags=["org"])


@router.get("/teams")
async def get_teams(request: Request):
    pool = await get_pool()
    teams = await list_teams(pool)
    return {"teams": teams}


@router.get("/advisors")
async def get_advisors(
    request: Request,
    team_id: str = Query(None),
):
    pool = await get_pool()
    advisors = await list_advisors(pool, team_id=team_id)
    return {"advisors": advisors}
