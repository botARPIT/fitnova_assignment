"""
FitNova Call Analysis — Phase 1
Two endpoints: /transcribe (Deepgram STT or WhisperX) and /flag (LangChain structured output)
"""

import logging
from contextlib import asynccontextmanager

import yaml
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from storage.local_store import LocalStore
from services.transcription_service import TranscriptionService
from routers import transcribe, flag

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


def load_company_facts() -> str:
    with open(settings.company_facts_path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Lifespan — dependency injection via app.state
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for shared resources."""
    # ── Startup ────────────────────────────────────────────────
    app.state.settings = settings
    app.state.rubric = load_rubric()
    app.state.company_facts = load_company_facts()
    app.state.store = LocalStore(
        upload_dir=settings.upload_dir,
        transcripts_dir=settings.transcripts_dir,
    )
    app.state.transcription_service = TranscriptionService(settings)

    log.info("FitNova started ✓")
    yield

    # ── Shutdown ───────────────────────────────────────────────
    app.state.transcription_service.cleanup()
    log.info("FitNova shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FitNova Call Analysis",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────
app.include_router(transcribe.router)
app.include_router(flag.router)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
