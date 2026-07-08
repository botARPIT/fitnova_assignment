# FitNova Project Context And Architecture

## Project Context
FitNova is a sales-call intelligence prototype for a fitness coaching business. The system accepts a recorded advisor-customer call, runs it through transcription and analysis, stores the result, and exposes it to a review dashboard.

The main product goals are:
- upload a call recording and analyze it end to end
- score the call on a fixed rubric
- generate evidence-backed issue flags
- let advisors contest flags
- let team leaders or directors resolve those contests
- expose org, team, advisor, and call-level analytics

## End-To-End Runtime Flow
The active upload path is:

1. `POST /api/calls/upload`
2. ingest uploaded audio and compute idempotency fingerprint
3. create or reuse a `calls` row
4. send audio to Deepgram for STT
5. send STT turns to LLM speaker repair
6. validate repaired conversation
7. send repaired transcript to analysis LLM
8. deterministically validate quotes, speaker/timestamp alignment, and selected company-facts rules
9. redact transcript text for persistence
10. save transcripts, report, and call status to PostgreSQL
11. expose the result to the frontend via `GET /api/calls/{id}`

## Backend Layering

### 1. Routers
Files:
- `backend/routers/calls.py`
- `backend/routers/reviews.py`
- `backend/routers/analytics.py`
- `backend/routers/org.py`

Responsibilities:
- define HTTP endpoints
- parse request params, bodies, and headers
- call services
- map domain errors to HTTP errors

Routers should stay thin. They should not contain SQL, pipeline orchestration, or review-state mutation logic.

### 2. Services
Files:
- `backend/services/pipeline_service.py`
- `backend/services/transcription_service.py`
- `backend/services/speaker_repair_service.py`
- `backend/services/tagging_service.py`
- `backend/services/persistence_service.py`
- `backend/services/call_service.py`
- `backend/services/review_service.py`
- `backend/services/analytics_service.py`
- `backend/services/org_service.py`

Responsibilities:
- orchestrate business workflows
- sequence vendor calls
- apply retry policy
- validate business rules
- coordinate repository calls

Service split:
- `pipeline_service.py`: upload-to-persistence orchestration
- `transcription_service.py`: Deepgram and WhisperX STT
- `speaker_repair_service.py`: LLM diarization repair
- `tagging_service.py`: call scoring and flag generation
- `persistence_service.py`: all write-side DB persistence for pipeline output
- `call_service.py`: read-side call aggregation for the UI
- `review_service.py`: contest and resolution workflow
- `analytics_service.py`: transforms repository data into typed analytics responses

### 3. Pipeline Helpers
Files:
- `backend/pipeline/context.py`
- `backend/pipeline/conversation_validator.py`
- `backend/pipeline/evidence_validator.py`
- `backend/pipeline/company_facts_validator.py`

Responsibilities:
- carry pipeline state
- perform deterministic validations after LLM steps
- keep post-processing logic separate from HTTP and SQL

### 4. Guardrails
Files:
- `backend/guardrails/prompts.py`
- `backend/guardrails/schemas.py`
- `backend/guardrails/validators.py`
- `backend/guardrails/input_guards.py`

Responsibilities:
- define LLM prompts
- define structured output schemas
- run validation before and after model calls

This is the contract boundary between prompt-based reasoning and deterministic code.

### 5. Repositories
Files:
- `backend/db/call_repository.py`
- `backend/db/transcript_repository.py`
- `backend/db/analysis_repository.py`
- `backend/db/review_repository.py`
- `backend/db/analytics_repository.py`

Responsibilities:
- contain SQL only
- map SQL rows to plain dicts
- avoid business branching

### 6. Schemas
Files:
- `backend/schemas/transcript.py`
- `backend/schemas/analytics.py`
- `backend/schemas/flags.py`
- `backend/guardrails/schemas.py`

Responsibilities:
- document shape contracts
- validate structured LLM output
- type API-level response models where needed

### 7. Utilities
Files:
- `backend/utils/retry.py`
- `backend/utils/deepgram_retry.py`
- `backend/utils/gemini_retry.py`
- `backend/utils/pii.py`
- `backend/utils/audio.py`
- `backend/logging_config.py`

Responsibilities:
- shared retry behavior
- vendor-specific retry classification
- PII redaction
- audio inspection helpers
- environment-aware logging policy

## Primary Input And Output Shapes

### Upload Input
Endpoint:
- `POST /api/calls/upload?advisor_id=<uuid>&organization_id=<uuid>`

Request:
- multipart form-data
- required file field: `file`
- optional query params:
  - `advisor_id`
  - `organization_id`

Output shape on success:

```json
{
  "call_id": "uuid",
  "status": "completed",
  "idempotent_reuse": false,
  "reused": false,
  "duration_sec": 188.2,
  "scores": {
    "needs_discovery": { "score": 1, "evidence": "..." },
    "product_knowledge": { "score": 3, "evidence": "..." },
    "objection_handling": { "score": 1, "evidence": "..." },
    "compliance": { "score": 0, "evidence": "..." },
    "next_step_booking": { "score": 2, "evidence": "..." }
  },
  "overall_score": 1.4,
  "flags": [],
  "discarded_flags": [],
  "transcript": {
    "raw": [],
    "diarized": []
  },
  "metadata": {
    "engine": "deepgram",
    "llm_model": "gemini-2.5-flash",
    "prompt_version": "v2.0",
    "rubric_version": "1.0",
    "company_facts_version": "1.0",
    "analysis_version": "1.0"
  },
  "timings": {
    "stt_ms": 0,
    "repair_ms": 0,
    "analysis_ms": 0,
    "total_ms": 0
  },
  "created_at": "..."
}
```

Conflict output when the same fingerprint is already processing:

```json
{
  "detail": {
    "call_id": "uuid",
    "status": "processing",
    "idempotent_reuse": false,
    "reused": false
  }
}
```

### Transcript Shape
File:
- `backend/schemas/transcript.py`

```json
{
  "speaker": "Advisor",
  "start": 12.4,
  "end": 16.1,
  "text": "..."
}
```

`TranscriptOut`:

```json
{
  "call_id": "uuid",
  "duration_sec": 188.2,
  "turns": [ { "speaker": "Advisor", "start": 0.0, "end": 2.1, "text": "..." } ],
  "engine": "deepgram"
}
```

### Speaker Repair LLM Output Shape
File:
- `backend/guardrails/schemas.py`

```json
{
  "turns": [
    {
      "speaker": "Advisor",
      "start": 0.0,
      "end": 2.1,
      "text": "..."
    }
  ]
}
```

### Analysis LLM Output Shape
File:
- `backend/guardrails/schemas.py`

```json
{
  "scores": {
    "needs_discovery": { "score": 0, "evidence": "..." },
    "product_knowledge": { "score": 0, "evidence": "..." },
    "objection_handling": { "score": 0, "evidence": "..." },
    "compliance": { "score": 0, "evidence": "..." },
    "next_step_booking": { "score": 0, "evidence": "..." }
  },
  "flags": [
    {
      "tag": "overpromising",
      "severity": "critical",
      "quote": "...",
      "explanation": "...",
      "timestamp": 37.4
    }
  ]
}
```

### Persisted Post-Validation Flag Shape
After deterministic validation, flags become `FlaggedFlag` objects:

```json
{
  "flag_id": "uuid",
  "tag": "overpromising",
  "severity": "critical",
  "quote": "...",
  "explanation": "...",
  "timestamp": 37.4,
  "match_score": 0.94,
  "discard_reason": null,
  "matched_turn_index": 12,
  "matched_turn_speaker": "Advisor",
  "matched_turn_start": 37.4
}
```

### Call Detail Output
Endpoint:
- `GET /api/calls/{call_id}`

Call detail is an assembled record from `calls`, `transcripts`, and `reports`, plus `effective_flags` added by `call_service.py`.

Important fields:
- `raw_transcript`
- `diarized_transcript`
- `scores`
- `flags`
- `discarded_flags`
- `effective_flags`
- `advisor_name`
- `team_name`
- `review_count`

`effective_flags` is derived from review history:
- no review -> `ACTIVE`
- pending review -> `CONTESTED`
- accepted review -> `ACTIVE`
- overturned review -> `OVERTURNED`

### Review Workflow Shapes

Contest request:

```http
POST /api/calls/{call_id}/flags/{flag_id}/contest
X-Advisor-ID: <advisor_uuid>
Content-Type: application/json
```

```json
{
  "contest_reason": "The quote is not actually a guarantee."
}
```

Resolve request:

```http
POST /api/reviews/{review_id}/decision
X-Advisor-ID: <team_leader_or_director_uuid>
Content-Type: application/json
```

```json
{
  "decision": "accepted",
  "decision_reason": "Quote is valid and policy breach stands."
}
```

## Database Schema Layout
Core tables:
- `organizations`
- `teams`
- `advisors`
- `calls`
- `transcripts`
- `reports`
- `flag_reviews`

Relationship overview:
- one organization has many teams
- one team has many advisors
- one advisor can own many calls
- one call has one transcript row
- one call has one report row
- one call can have many `flag_reviews`

Data ownership:
- `calls`: ingestion identity, advisor/team linkage, status, audio path
- `transcripts`: raw STT turns, repaired turns, metadata, timings
- `reports`: scores, overall score, verified flags, discarded flags
- `flag_reviews`: advisor contest records and resolver decisions

## Where The Main Business Logic Lives
- upload orchestration: `backend/services/pipeline_service.py`
- deterministic flag checks: `backend/pipeline/evidence_validator.py`
- company policy contradictions: `backend/pipeline/company_facts_validator.py`
- review workflow: `backend/services/review_service.py`
- read-model assembly for the frontend: `backend/services/call_service.py`

## Current Provider Behavior
- STT: Deepgram
- speaker repair: OpenAI GPT-4o mini primary, Gemini fallback
- analysis: Gemini structured output

## Logging Model
- development: detailed logs allowed, including corrected diarization output if enabled
- production: only necessary operational logs, no transcript or quote content, no raw LLM output payloads
