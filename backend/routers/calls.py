"""API endpoints for the call pipeline and call CRUD."""

import mimetypes

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from errors import CallConflictError

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.post("/upload")
async def upload_call(
    request: Request,
    file: UploadFile,
    advisor_id: str = Query(None),
    organization_id: str = Query(None),
):
    """Full pipeline: upload → transcribe → analyze → store.

    Idempotent: uploading the same file twice returns the existing result.
    Organization_id defaults to FitNova's default org.
    """
    pipeline = request.app.state.pipeline_service
    try:
        result = await pipeline.process_call(
            file=file,
            advisor_id=advisor_id,
            organization_id=organization_id,
        )
        return result
    except CallConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "call_id": e.call_id,
                "status": "processing",
                "idempotent_reuse": False,
                "reused": False,
            },
        )


@router.get("")
async def list_calls_endpoint(
    request: Request,
    advisor_id: str = Query(None),
    team_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    service = request.app.state.call_service
    return await service.list_calls(
        advisor_id=advisor_id,
        team_id=team_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{call_id}")
async def get_call_endpoint(call_id: str, request: Request):
    service = request.app.state.call_service
    call = await service.get_call_detail(call_id)
    if not call:
        raise HTTPException(404, "Call not found.")

    return call


@router.get("/{call_id}/audio")
async def get_call_audio_endpoint(call_id: str, request: Request):
    service = request.app.state.call_service
    audio_path = await service.get_call_audio_path(call_id)
    if not audio_path or not audio_path.exists():
        raise HTTPException(404, "Call audio not found.")

    media_type, _encoding = mimetypes.guess_type(str(audio_path))
    return FileResponse(
        path=audio_path,
        media_type=media_type or "application/octet-stream",
        filename=audio_path.name,
    )
