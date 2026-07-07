# Task 04: Backend Pipeline Integration + New API Endpoints

## Objective
Wire the full end-to-end pipeline: upload → transcribe → speaker repair → analyze → store in DB → return results. Add new API routers for calls, org structure, and integrate everything into `main.py`.

## Parallelization
**Group B** — Depends on Tasks 01 (database), 02 (speaker repair), and 03 (ingestion).

## Context
Currently the backend has two disconnected endpoints (`/transcribe` and `/flag`). We need a unified pipeline endpoint (`POST /api/calls/upload`) that runs the complete flow and stores everything in PostgreSQL.

The existing `/transcribe` and `/flag` endpoints should be KEPT as-is for backward compatibility and testing.

## Files to Create

### 1. `backend/schemas/api.py`

New request/response Pydantic models for the API:

```python
"""Request/Response schemas for the new API endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Call Schemas ─────────────────────────────────────────────

class CallUploadResponse(BaseModel):
    """Response from POST /api/calls/upload — full pipeline result."""
    call_id: str
    status: str
    duration_sec: float | None
    language: str | None
    advisor_name: str | None
    transcript: dict  # diarized transcript turns
    report: dict | None  # scores + flags (None if analysis failed)


class CallListItem(BaseModel):
    """Single item in the call listing."""
    id: str
    status: str
    duration_sec: float | None
    language: str | None
    created_at: datetime
    completed_at: datetime | None
    advisor_name: str | None
    team_name: str | None
    overall_score: float | None
    review_count: int


class CallDetail(BaseModel):
    """Full call detail including transcript, report, and reviews."""
    id: str
    status: str
    duration_sec: float | None
    language: str | None
    created_at: datetime
    completed_at: datetime | None
    advisor_name: str | None
    team_name: str | None
    raw_transcript: dict | list | None
    diarized_transcript: dict | list | None
    engine: str | None
    scores: dict | None
    overall_score: float | None
    flags: list | None
    discarded_flags: list | None
    reviews: list | None


# ── Flag Contest Schemas ─────────────────────────────────────

class ContestFlagRequest(BaseModel):
    flag_index: int
    reason: str
    reviewer_id: str | None = None


class ContestFlagResponse(BaseModel):
    review_id: str
    decision: str
    status: str = "contested"


class ReviewFlagRequest(BaseModel):
    decision: str  # 'accepted' or 'overturned'


# ── Org Schemas ──────────────────────────────────────────────

class TeamOut(BaseModel):
    id: str
    name: str
    advisor_count: int


class AdvisorOut(BaseModel):
    id: str
    name: str
    role: str
    team_id: str | None = None
```

### 2. `backend/routers/calls.py`

The main pipeline router. This is the most critical file.

```python
"""Call upload, processing pipeline, and CRUD endpoints."""

import logging

from fastapi import APIRouter, UploadFile, Form, HTTPException, Request

from schemas.transcript import Turn, TranscriptOut
from services.speaker_repair_service import repair_speakers
from services.tagging_service import analyze_call
from services.ingestion import FileUploadAdapter
from db.connection import get_pool
from db import repository as repo

log = logging.getLogger("fitnova.routes.calls")
router = APIRouter(prefix="/api/calls", tags=["calls"])

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


@router.post("/upload")
async def upload_and_process(
    request: Request,
    file: UploadFile,
    advisor_id: str = Form(None),
):
    """Full pipeline: upload → transcribe → speaker repair → analyze → store.
    
    This is the main entry point for processing a sales call.
    """
    settings = request.app.state.settings
    stt = request.app.state.transcription_service
    rubric = request.app.state.rubric
    company_facts = request.app.state.company_facts
    pool = await get_pool()

    # ── 1. Ingest ─────────────────────────────────────────────
    raw_bytes = await file.read()
    adapter = FileUploadAdapter(settings.upload_dir)
    
    try:
        metadata = await adapter.ingest(
            filename=file.filename,
            raw_bytes=raw_bytes,
            advisor_id=advisor_id,
            organization_id=DEFAULT_ORG_ID,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # ── 2. Create call record ─────────────────────────────────
    call_row = await repo.create_call(
        pool,
        organization_id=DEFAULT_ORG_ID,
        advisor_id=advisor_id,
        audio_path=metadata.audio_path,
    )
    call_id = str(call_row["id"])

    try:
        # ── 3. Transcribe (Deepgram) ──────────────────────────
        log.info(f"[{call_id}] Starting Deepgram transcription...")
        raw_turns, duration, response = stt.transcribe_deepgram(raw_bytes)

        if duration < settings.min_duration_sec:
            raise ValueError(
                f"Audio too short ({duration:.1f}s). "
                f"Minimum {settings.min_duration_sec}s — likely a misdial."
            )

        # ── 4. Speaker Repair (Gemini) ────────────────────────
        log.info(f"[{call_id}] Repairing speaker labels...")
        diarized_turns = repair_speakers(raw_turns, settings.google_api_key)

        # ── 5. Store transcript ───────────────────────────────
        raw_turns_dicts = [t.model_dump() for t in raw_turns]
        diarized_turns_dicts = [t.model_dump() for t in diarized_turns]
        
        await repo.save_transcript(
            pool,
            call_id=call_id,
            raw_transcript=raw_turns_dicts,
            diarized_transcript=diarized_turns_dicts,
            engine="deepgram",
        )

        # ── 6. Analyze (Gemini) ───────────────────────────────
        log.info(f"[{call_id}] Running quality analysis...")
        transcript_out = TranscriptOut(
            call_id=call_id,
            duration_sec=round(duration, 2),
            turns=diarized_turns,
            engine="deepgram",
        )
        
        scores_dict, overall, verified_flags, discarded_flags = analyze_call(
            transcript=transcript_out,
            rubric=rubric,
            company_facts=company_facts,
            google_api_key=settings.google_api_key,
            quote_match_threshold=settings.quote_match_threshold,
        )

        # ── 7. Store report ───────────────────────────────────
        verified_dicts = [f.model_dump() for f in verified_flags]
        discarded_dicts = [f.model_dump() for f in discarded_flags]

        await repo.save_report(
            pool,
            call_id=call_id,
            scores=scores_dict,
            overall_score=overall,
            flags=verified_dicts,
            discarded_flags=discarded_dicts,
        )

        # ── 8. Mark complete ──────────────────────────────────
        await repo.update_call_status(
            pool, call_id, "completed",
            duration_sec=round(duration, 2),
        )

        log.info(f"[{call_id}] Pipeline complete ✓ score={overall}")

        return {
            "call_id": call_id,
            "status": "completed",
            "duration_sec": round(duration, 2),
            "transcript": {
                "turns": diarized_turns_dicts,
                "turn_count": len(diarized_turns),
            },
            "report": {
                "scores": scores_dict,
                "overall_score": overall,
                "flags": verified_dicts,
                "discarded_flags": discarded_dicts,
            },
        }

    except Exception as e:
        log.error(f"[{call_id}] Pipeline failed: {e}", exc_info=True)
        await repo.update_call_status(
            pool, call_id, "failed",
            error_message=str(e),
        )
        raise HTTPException(502, f"Processing failed: {e}")


@router.get("")
async def list_calls(
    request: Request,
    advisor_id: str | None = None,
    team_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List calls with optional filtering."""
    pool = await get_pool()
    calls = await repo.list_calls(
        pool,
        advisor_id=advisor_id,
        team_id=team_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    # Convert UUIDs and datetimes to strings for JSON
    for c in calls:
        for key in c:
            if hasattr(c[key], 'hex'):  # UUID
                c[key] = str(c[key])
            elif hasattr(c[key], 'isoformat'):  # datetime
                c[key] = c[key].isoformat()
    return {"calls": calls, "count": len(calls)}


@router.get("/{call_id}")
async def get_call(request: Request, call_id: str):
    """Get full call detail with transcript, report, and reviews."""
    pool = await get_pool()
    call = await repo.get_call(pool, call_id)
    if not call:
        raise HTTPException(404, f"Call {call_id} not found")
    
    reviews = await repo.list_flag_reviews(pool, call_id)
    
    # Convert UUIDs and datetimes
    for key in call:
        if hasattr(call[key], 'hex'):
            call[key] = str(call[key])
        elif hasattr(call[key], 'isoformat'):
            call[key] = call[key].isoformat()
    
    for r in reviews:
        for key in r:
            if hasattr(r[key], 'hex'):
                r[key] = str(r[key])
            elif hasattr(r[key], 'isoformat'):
                r[key] = r[key].isoformat()
    
    call["reviews"] = reviews
    return call
```

### 3. `backend/routers/org.py`

```python
"""Org structure endpoints — teams and advisors."""

import logging

from fastapi import APIRouter, Request

from db.connection import get_pool
from db import repository as repo

log = logging.getLogger("fitnova.routes.org")
router = APIRouter(prefix="/api/org", tags=["organization"])


@router.get("/teams")
async def list_teams(request: Request):
    pool = await get_pool()
    teams = await repo.list_teams(pool)
    for t in teams:
        for key in t:
            if hasattr(t[key], 'hex'):
                t[key] = str(t[key])
    return {"teams": teams}


@router.get("/advisors")
async def list_advisors(request: Request, team_id: str | None = None):
    pool = await get_pool()
    advisors = await repo.list_advisors(pool, team_id)
    for a in advisors:
        for key in a:
            if hasattr(a[key], 'hex'):
                a[key] = str(a[key])
            elif hasattr(a[key], 'isoformat'):
                a[key] = a[key].isoformat()
    return {"advisors": advisors}
```

## Files to Modify

### 4. `backend/main.py`

Add the following changes:

1. **Import new routers and DB module:**
```python
from routers import calls, org
from db.connection import init_pool, close_pool
```

2. **In the `lifespan` function, after existing startup code:**
```python
# ── Database ──────────────────────────────────────────────
await init_pool(settings.database_url)
```

3. **In the `lifespan` function, in the shutdown section (before existing cleanup):**
```python
await close_pool()
```

4. **Register new routers (after existing router registrations):**
```python
app.include_router(calls.router)
app.include_router(org.router)
```

## Important Notes

- The existing `/transcribe` and `/flag` endpoints must remain untouched.
- UUID serialization: `asyncpg` returns `UUID` objects. Convert to strings before JSON response.
- Datetime serialization: Similarly, convert `datetime` objects to ISO strings.
- The pipeline is synchronous within a single request — no background workers.
- Errors at any stage mark the call as `failed` in the DB with the error message.

## Acceptance Criteria
1. `POST /api/calls/upload` runs the full pipeline and returns structured results
2. `GET /api/calls` returns paginated call listing with optional filters
3. `GET /api/calls/{id}` returns full detail with transcript + report + reviews
4. `GET /api/org/teams` lists all teams
5. `GET /api/org/advisors` lists advisors with optional team filter
6. Failed pipeline stages set `calls.status = 'failed'` with error message
7. Existing `/transcribe` and `/flag` endpoints still work
