"""
FitNova Call Analysis — Phase 2
Full pipeline: upload → transcribe → repair → analyze → persist
Plus legacy /transcribe and /flag endpoints.
"""

import logging
from contextlib import asynccontextmanager

import yaml
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from db.connection import init_pool, close_pool
from db import run_migrations
from errors import (
    AudioValidationError, IngestionError, TranscriptionError,
    SpeakerRepairError, ConversationValidationError, AnalysisError,
    PersistenceError, PipelineError,
    ReviewError, ReviewPermissionError, ReviewNotFoundError,
)
from storage.local_store import LocalStore
from services.transcription_service import TranscriptionService
from services.pipeline_service import PipelineService
from services.analytics_service import AnalyticsService
from routers import transcribe, flag, calls, org, analytics, reviews

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger("fitnova")


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def load_rubric() -> dict:
    with open(settings.rubric_path) as f:
        return yaml.safe_load(f)


def load_company_facts() -> dict:
    with open(settings.company_facts_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

HANDLED_ERRORS = [
    (AudioValidationError, 422),
    (IngestionError, 500),
    (TranscriptionError, 502),
    (SpeakerRepairError, 502),
    (ConversationValidationError, 422),
    (AnalysisError, 502),
    (PersistenceError, 500),
    (ReviewError, 400),
    (ReviewPermissionError, 403),
    (ReviewNotFoundError, 404),
]


def register_error_handlers(app: FastAPI):
    for exc_cls, status in HANDLED_ERRORS:
        def make_handler(status_code: int):
            def handler(_request: Request, exc: PipelineError):
                return JSONResponse(
                    status_code=status_code,
                    content={"detail": exc.detail},
                )
            return handler
        app.add_exception_handler(exc_cls, make_handler(status))


# ---------------------------------------------------------------------------
# Lifespan — dependency injection via app.state
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for shared resources."""
    # ── Startup ────────────────────────────────────────────────
    rubric = load_rubric()
    company_facts = load_company_facts()

    app.state.settings = settings
    app.state.rubric = rubric
    app.state.company_facts = company_facts
    app.state.store = LocalStore(
        upload_dir=settings.upload_dir,
        transcripts_dir=settings.transcripts_dir,
    )
    app.state.transcription_service = TranscriptionService(settings)

    # Pipeline orchestration
    app.state.pipeline_service = PipelineService(
        settings=settings,
        rubric=rubric,
        company_facts=company_facts,
    )

    # Database pool
    pool = await init_pool(settings.database_url)
    log.info("Database pool initialized ✓")

    # Auto-apply pending migrations
    n = await run_migrations(pool)
    if n:
        log.info("Applied %d pending migration(s)", n)

    # Analytics service
    app.state.analytics_service = AnalyticsService(
        pool=pool,
        org_id=settings.default_org_id,
    )
    log.info("AnalyticsService initialized ✓")

    log.info("FitNova started ✓")
    yield

    # ── Shutdown ───────────────────────────────────────────────
    app.state.transcription_service.cleanup()
    await close_pool()
    log.info("FitNova shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FitNova Call Analysis Pipeline",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

# ── Register routers ──────────────────────────────────────────
app.include_router(transcribe.router)   # legacy POST /transcribe
app.include_router(flag.router)         # legacy POST /flag
app.include_router(calls.router)        # POST /api/calls/upload, GET /api/calls, GET /api/calls/{id}
app.include_router(org.router)          # GET /api/org/teams, GET /api/org/advisors
app.include_router(analytics.router)    # GET /api/analytics/*
app.include_router(reviews.router)      # POST /api/calls/{id}/flags/{flag_id}/contest, etc.


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
