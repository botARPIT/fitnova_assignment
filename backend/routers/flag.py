"""POST /flag — Run LLM quality analysis on a transcript."""

import logging

from fastapi import APIRouter, HTTPException, Request

from schemas.flags import FlagRequest, FlagResponse
from schemas.transcript import TranscriptOut
from services.tagging_service import analyze_call

log = logging.getLogger("fitnova.routes.flag")

router = APIRouter()


@router.post("/flag", response_model=FlagResponse)
async def flag_call(req: FlagRequest, request: Request):
    # ── Resolve dependencies from app.state ────────────────────
    settings = request.app.state.settings
    store = request.app.state.store
    rubric = request.app.state.rubric
    company_facts = request.app.state.company_facts

    # ── Resolve transcript ─────────────────────────────────────
    if req.transcript:
        transcript = req.transcript
    elif req.call_id:
        transcript = store.read_transcript(req.call_id)
        if transcript is None:
            raise HTTPException(404, f"No transcript found for call_id={req.call_id}")
    else:
        raise HTTPException(400, "Provide either 'transcript' or 'call_id'")

    # ── Run analysis ───────────────────────────────────────────
    try:
        scores_dict, overall, verified_flags, discarded_flags = analyze_call(
            transcript=transcript,
            rubric=rubric,
            company_facts=company_facts,
            google_api_key=settings.google_api_key,
            quote_match_threshold=settings.quote_match_threshold,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    return FlagResponse(
        call_id=transcript.call_id,
        scores=scores_dict,
        overall_score=overall,
        flags=verified_flags,
        discarded_flags=discarded_flags,
    )
