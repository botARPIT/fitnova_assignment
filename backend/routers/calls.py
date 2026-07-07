"""API endpoints for the call pipeline and call CRUD.

Thin routers — no business logic, no repository calls.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile

from errors import PipelineError
from db.call_repository import get_call, list_calls
from db.connection import get_pool
from services import review_service

log = logging.getLogger("fitnova.routers.calls")

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.post("/upload")
async def upload_call(
    request: Request,
    file: UploadFile,
    advisor_id: str = Query(None),
):
    """Full pipeline: upload → transcribe → analyze → store."""
    pipeline = request.app.state.pipeline_service
    result = await pipeline.process_call(
        file=file,
        advisor_id=advisor_id,
    )
    return result


@router.get("")
async def list_calls_endpoint(
    request: Request,
    advisor_id: str = Query(None),
    team_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    calls = await list_calls(
        pool,
        advisor_id=advisor_id,
        team_id=team_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"calls": calls, "count": len(calls), "limit": limit, "offset": offset}


@router.get("/{call_id}")
async def get_call_endpoint(call_id: str, request: Request):
    pool = await get_pool()
    call = await get_call(pool, call_id)
    if not call:
        raise HTTPException(404, f"Call {call_id} not found")

    # Compute effective flag statuses from review history
    original_flags = call.get("flags") or []
    if original_flags:
        effective = await review_service.compute_effective_flags(
            pool, call_id, original_flags,
        )
        call["effective_flags"] = effective
    else:
        call["effective_flags"] = []

    return call
