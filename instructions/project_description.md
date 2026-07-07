# FitNova Sales Intelligence System — Project Description & LLD

## Overview
FitNova is a fitness coaching company. Their sales advisors make calls to convert leads into subscribers. This system automatically analyzes recorded sales calls to:
1. **Transcribe** audio using Deepgram Nova-3
2. **Re-diarize** speakers using Gemini (mono audio diarization is unreliable)
3. **Score** call quality across 5 rubric dimensions
4. **Flag** policy violations and coaching opportunities
5. **Store** everything in PostgreSQL for org-wide analytics
6. **Enable** flag contestation (advisors can challenge machine-generated flags)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Dashboard (Vite)                      │
│   Dashboard │ Call List │ Call Detail │ Upload │ Team Analytics  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────────────┐      │
│  │ Ingestion   │→ │ Transcription │→ │ Speaker Repair   │      │
│  │ (Adapters)  │  │ (Deepgram)    │  │ (Gemini 2.5)     │      │
│  └─────────────┘  └───────────────┘  └────────┬─────────┘      │
│                                               │                 │
│                                    ┌──────────▼─────────┐      │
│                                    │ Quality Analysis   │      │
│                                    │ (Gemini 2.5)       │      │
│                                    │ - 5D Scoring       │      │
│                                    │ - Flag Detection   │      │
│                                    │ - Quote Verify     │      │
│                                    └──────────┬─────────┘      │
│                                               │                 │
│                                    ┌──────────▼─────────┐      │
│                                    │  Repository Layer  │      │
│                                    │  (asyncpg)         │      │
│                                    └──────────┬─────────┘      │
└───────────────────────────────────────────────┼────────────────┘
                                                │
                              ┌─────────────────▼─────────────┐
                              │   PostgreSQL 16 (Docker)      │
                              │   organizations → teams →     │
                              │   advisors → calls →          │
                              │   transcripts → reports →     │
                              │   flag_reviews                │
                              └───────────────────────────────┘
```

---

## Database Schema (PostgreSQL)

```sql
-- Org hierarchy
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE advisors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id),
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'junior',  -- junior | senior | team_lead
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Call processing
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    advisor_id UUID REFERENCES advisors(id),
    audio_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing',  -- processing | completed | failed
    duration_sec FLOAT,
    language TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID UNIQUE REFERENCES calls(id),
    raw_transcript JSONB,      -- Original STT output
    diarized_transcript JSONB,  -- After speaker repair
    engine TEXT NOT NULL,       -- deepgram | whisperx
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID UNIQUE REFERENCES calls(id),
    scores JSONB NOT NULL,          -- Per-dimension scores
    overall_score FLOAT NOT NULL,
    flags JSONB DEFAULT '[]',       -- Active flags
    discarded_flags JSONB DEFAULT '[]',  -- Quotes that failed verification
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Contestation workflow
CREATE TABLE flag_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    flag_index INT NOT NULL,
    reviewer_id UUID REFERENCES advisors(id),
    decision TEXT NOT NULL DEFAULT 'contested',  -- contested | accepted | overturned
    reason TEXT,
    reviewed_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX idx_calls_org ON calls(organization_id);
CREATE INDEX idx_calls_advisor ON calls(advisor_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_flag_reviews_call ON flag_reviews(call_id);

-- Seed data
INSERT INTO organizations (id, name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'FitNova');

INSERT INTO teams (id, organization_id, name) VALUES
    ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'Pod Alpha'),
    ('00000000-0000-0000-0000-000000000020', '00000000-0000-0000-0000-000000000001', 'Pod Beta');

INSERT INTO advisors (id, team_id, name, role) VALUES
    ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000010', 'Priya Sharma', 'team_lead'),
    ('00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000010', 'Arjun Mehta', 'senior'),
    ('00000000-0000-0000-0000-000000000103', '00000000-0000-0000-0000-000000000010', 'Neha Gupta', 'junior'),
    ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000020', 'Vikram Patel', 'team_lead'),
    ('00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000020', 'Ananya Singh', 'senior'),
    ('00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000020', 'Rohit Kumar', 'junior');
```

---

## Pipeline (Synchronous)

```
POST /api/calls/upload
  ↓
1. INGEST: FileUploadAdapter saves audio, returns CallMetadata
  ↓
2. DB: Create call record (status='processing')
  ↓
3. TRANSCRIBE: Deepgram Nova-3 (multilingual, diarization)
  ↓
4. SPEAKER REPAIR: Gemini re-labels speakers → Advisor/Customer
  ↓
5. DB: Store raw + diarized transcript
  ↓
6. ANALYZE: Gemini scores 5 dimensions + flags violations
  ↓
7. QUOTE VERIFY: Check flag quotes exist in transcript (fuzzy match)
  ↓
8. DB: Store report (scores + verified flags + discarded flags)
  ↓
9. DB: Update call status → completed
  ↓
RETURN: Full result to frontend
```

On failure at any stage → `status='failed'` with error message.

---

## Scoring Dimensions (0-5 scale)

| Dimension | What it measures |
|-----------|-----------------|
| `needs_discovery` | Did advisor ask about goals, budget, schedule, health? |
| `product_knowledge` | Were plans, pricing, features represented accurately? |
| `objection_handling` | Were customer concerns addressed empathetically? |
| `compliance` | Were policies followed? No false guarantees or pressure? |
| `next_step_booking` | Did advisor guide toward booking a free trial? |

**Overall Score** = mean of 5 dimension scores

---

## Issue Tags

```
no_needs_discovery, overpromising, pressure_or_urgency_tactics,
price_before_value, undisclosed_costs, weak_or_missing_trial_booking,
talking_over_customer
```

---

## API Endpoints

### Pipeline
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/calls/upload` | Full pipeline: upload → transcribe → analyze → store |

### Calls CRUD
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/calls` | List calls (filters: advisor_id, team_id, status) |
| `GET` | `/api/calls/{id}` | Full call detail with transcript + report |

### Flag Contestation
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/calls/{id}/contest-flag` | Contest a flag |
| `PATCH` | `/api/calls/{id}/reviews/{reviewId}` | Accept or overturn a contest |
| `GET` | `/api/calls/{id}/reviews` | List flag reviews |

### Organization
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/org/teams` | List teams |
| `GET` | `/api/org/advisors` | List advisors (filter: team_id) |

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/analytics/overview` | Org-wide metrics + top flags |
| `GET` | `/api/analytics/teams/{id}` | Team leaderboard by avg score |
| `GET` | `/api/analytics/advisors/{id}` | Advisor stats + flag frequency |

### Legacy (backward-compatible)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/transcribe` | Transcribe-only (existing) |
| `POST` | `/flag` | Analyze-only (existing) |

---

## Task Breakdown & Parallelization

```
Group A (No dependencies — start immediately):
  ├── Task 01: Docker + PostgreSQL + Repository Layer
  ├── Task 02: LLM Speaker Repair Service
  ├── Task 03: Source-Agnostic Ingestion Layer
  └── Task 08: Tagging Service Enhancement

Group B (Depends on Group A):
  ├── Task 04: Backend Pipeline Integration + API
  ├── Task 05: Flag Contestation Workflow
  └── Task 06: Analytics API

Group C (Depends on Group B):
  └── Task 07: Frontend Multi-Page Dashboard
```

**Estimated time**: ~8-10 hours with parallel execution.

---

## Environment Variables

```env
DEEPGRAM_API_KEY=...          # Deepgram STT
GOOGLE_API_KEY=...            # Gemini (speaker repair + analysis)
HF_TOKEN=...                  # HuggingFace (WhisperX/Pyannote, optional)
DATABASE_URL=postgresql://fitnova:fitnova_dev@localhost:5432/fitnova
QUOTE_MATCH_THRESHOLD=0.6     # Fuzzy match threshold for quote verification
MIN_DURATION_SEC=10            # Minimum call duration (reject misdials)
```

---

## Key Design Decisions

1. **Synchronous pipeline**: No Celery/Redis. The 12-hour timeline doesn't allow for async worker infrastructure. The pipeline runs within a single HTTP request (~20-30s for a 5-min call).

2. **LLM speaker repair is mandatory**: Deepgram's acoustic diarization fails on mono audio (assigns 90%+ of turns to one speaker). Gemini re-diarization achieves ~90% accuracy on our test set.

3. **Anti-hallucination**: Every LLM-generated flag must include a quote that fuzzy-matches against the actual transcript. Failed matches are discarded with a reason logged.

4. **Source-agnostic ingestion**: Adapter pattern means switching from file upload to Twilio webhooks requires only implementing a new adapter class — no pipeline changes.

5. **Flat UUIDs with seed data**: Predictable UUIDs for seed data makes testing and frontend development easier.
