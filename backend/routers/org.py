"""API endpoints for org hierarchy (teams, advisors)."""

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/org", tags=["org"])


@router.get("/teams")
async def get_teams(request: Request):
    service = request.app.state.org_service
    return await service.list_teams()


@router.get("/advisors")
async def get_advisors(
    request: Request,
    team_id: str = Query(None),
):
    service = request.app.state.org_service
    return await service.list_advisors(team_id=team_id)
