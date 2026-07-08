"""
FitNova Call Analysis — Phase 2
Full pipeline: upload → transcribe → repair → analyze → persist.
"""

import logging
from contextlib import asynccontextmanager

import yaml
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.connection import init_pool, close_pool
from db import run_migrations
from logging_config import configure_logging
from error_middleware import register_error_handlers
from services.call_service import CallService
from services.pipeline_service import PipelineService
from services.analytics_service import AnalyticsService
from services.org_service import OrgService
from routers import calls, org, analytics, reviews

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

configure_logging(settings)
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
    # Pipeline orchestration
    app.state.pipeline_service = PipelineService(
        settings=settings,
        rubric=rubric,
        company_facts=company_facts,
    )
    app.state.transcription_service = app.state.pipeline_service.stt

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
    app.state.call_service = CallService(pool=pool)
    app.state.org_service = OrgService(pool=pool)
    log.info("AnalyticsService initialized ✓")

    log.info("FitNova started ✓")
    yield

    # ── Shutdown ───────────────────────────────────────────────
    app.state.pipeline_service.stt.cleanup()
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

register_error_handlers(app, settings)

# ── Register routers ──────────────────────────────────────────
app.include_router(calls.router)        # POST /api/calls/upload, GET /api/calls, GET /api/calls/{id}
app.include_router(org.router)          # GET /api/org/teams, GET /api/org/advisors
app.include_router(analytics.router)    # GET /api/analytics/*
app.include_router(reviews.router)      # POST /api/calls/{id}/flags/{flag_id}/contest, etc.


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
