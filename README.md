# FitNova Sales Call Intelligence Prototype

## Overview
This project is a working prototype for FitNova's AI-assisted sales-call review workflow. A call recording is uploaded, transcribed, speaker-repaired, analyzed against a rubric, persisted in PostgreSQL, and surfaced in a React dashboard for org, team, advisor, and call-level review.

## Features
- Source-agnostic ingestion interface with file upload implemented
- Deepgram transcription with OpenAI GPT-4o mini primary speaker repair and Gemini fallback
- Structured scoring across five rubric dimensions
- Quote-backed issue flags with anti-hallucination verification
- Advisor flag contestation and team-leader review workflow
- Org, team, advisor, and call-detail dashboards
- Idempotent call processing, vendor retries, and transcript PII redaction

## Architecture
- `backend/`
  - FastAPI app, pipeline orchestration, repositories, migrations, guardrails
- `frontend/`
  - React + Vite dashboard for upload, analytics, and review flows
- `backend/db/schema.sql`
  - Base PostgreSQL schema used by Docker init
- `backend/db/migrations/`
  - Incremental schema alignment applied on startup

## Tech Stack
- Backend: FastAPI, asyncpg, LangChain OpenAI + Google GenAI, Deepgram SDK
- Frontend: React, React Router, Vite
- Database: PostgreSQL 16

## Prerequisites
- Python 3.10+
- Node.js 20+
- npm
- Docker and Docker Compose
- Deepgram API key
- Google API key for Gemini
- OpenAI API key if you want GPT-4o mini as the primary speaker-repair model

## Environment Setup
Create `backend/.env` with at least:

```env
DEEPGRAM_API_KEY=your_key
GOOGLE_API_KEY=your_key
DATABASE_URL=postgresql://fitnova:fitnova_dev@localhost:5432/fitnova
HOST=0.0.0.0
PORT=8000
APP_ENV=development
```

Optional runtime settings:

```env
MIN_DURATION_SEC=10
QUOTE_MATCH_THRESHOLD=0.6
DEEPGRAM_MAX_RETRIES=3
GEMINI_MAX_RETRIES=2
RETRY_BASE_DELAY_MS=1000
DEEPGRAM_MODEL=nova-3
DEEPGRAM_DIARIZE_MODEL=latest
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
SPEAKER_REPAIR_PRIMARY_MODEL=openai/gpt-4o-mini
SPEAKER_REPAIR_MODEL=gemini-2.5-flash
ANALYSIS_MODEL=gemini-2.5-flash
```

Speaker-repair provider behavior:
- If `OPENAI_API_KEY` is present, diarization repair uses `SPEAKER_REPAIR_PRIMARY_MODEL` first.
- If that call fails, it falls back to Gemini via `SPEAKER_REPAIR_MODEL`.
- If `OPENAI_API_KEY` is absent, Gemini is used directly.

## Running the Database
From the repo root:

```bash
docker compose up -d
```

This starts PostgreSQL and loads `backend/db/schema.sql` on first boot.

## Running the Backend
From `backend/`:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On startup the backend applies any pending SQL migrations from `backend/db/migrations/`.

Backend verification from `backend/`:

```bash
source venv/bin/activate
python -m py_compile $(find . -name '*.py')
PYTHONPATH=. pytest tests/test_retry.py
```

Note:
- A dedicated backend linter such as `ruff` or `flake8` is not currently configured in the repo.
- The current static verification baseline is import/compile validation plus targeted tests.

## Running the Frontend
From `frontend/`:

```bash
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

For production or Vercel deployment, set `VITE_API_BASE_URL` to the public backend origin.

## Demo Flow
1. Start PostgreSQL with Docker.
2. Start the FastAPI backend.
3. Start the Vite frontend.
4. Open the upload page and submit a supported call recording (`wav`, `mp3`, `m4a`).
5. Wait for STT transcription, LLM speaker repair, analysis, and persistence.
6. Open the call detail page to inspect transcript, scores, flags, and review history.
7. Use the acting-advisor selector to contest a flag or resolve a pending review.
8. Visit the dashboard and team pages to inspect org/team/advisor analytics.

## Real vs Mocked
### Real
- FastAPI backend and PostgreSQL persistence
- Deepgram transcription
- GPT-4o mini via OpenAI as primary speaker repair, with Gemini fallback
- Gemini-based structured analysis
- Quote verification and persisted reports
- React dashboard and review flows

### Mocked / Stubbed / Simplified
- No production authentication; actor identity is selected manually in the UI
- Webhook and CRM ingestion adapters are defined but not implemented
- PII redaction is text-based only; audio is not redacted
- Non-sales-call detection is still heuristic rather than a dedicated classifier

## Known Limitations
- The prototype is synchronous; large uploads block until analysis completes.
- The active demo path is Deepgram transcription followed by LLM speaker repair and analysis.
- Retry policies are intentionally small and tuned for demo reliability, not production throughput.
- Organization/team/advisor data is seeded and minimal.

## Submission Notes
- `WRITEUP.md` contains the design tradeoffs and what remains incomplete.
- `frontend/README.md` contains the frontend-specific routes and runtime notes.
- `PROJECT_CONTEXT_AND_ARCHITECTURE.md` documents the backend layers, schemas, and request/response shapes.
