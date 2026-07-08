-- === ORG HIERARCHY ===

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE advisors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'advisor'
        CHECK (role IN ('advisor', 'team_leader', 'director', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- === CALL DATA ===

CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    advisor_id UUID REFERENCES advisors(id),
    audio_path TEXT NOT NULL,
    file_sha256 TEXT,
    source TEXT NOT NULL DEFAULT 'FILE_UPLOAD',
    external_call_id TEXT,
    ingestion_fingerprint TEXT,
    duration_sec FLOAT,
    language TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'processing', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    failed_stage TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID UNIQUE NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    raw_transcript JSONB NOT NULL,
    diarized_transcript JSONB NOT NULL,
    engine TEXT NOT NULL DEFAULT 'deepgram',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    timings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID UNIQUE NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    scores JSONB NOT NULL,
    overall_score FLOAT NOT NULL,
    flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    discarded_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- === FLAG CONTESTATION WORKFLOW ===

CREATE TABLE flag_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    flag_id UUID NOT NULL,
    advisor_id UUID REFERENCES advisors(id),
    team_leader_id UUID REFERENCES advisors(id),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'ACCEPTED', 'OVERTURNED')),
    contest_reason TEXT,
    decision_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- === SEED DATA ===

INSERT INTO organizations (id, name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'FitNova');

INSERT INTO teams (id, organization_id, name) VALUES
    ('22222222-2222-2222-2222-222222222221', '11111111-1111-1111-1111-111111111111', 'Pod Alpha'),
    ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'Pod Beta');

INSERT INTO advisors (id, team_id, name, role) VALUES
    ('33333333-3333-3333-3333-333333333331', '22222222-2222-2222-2222-222222222221', 'Saad Khan', 'advisor'),
    ('33333333-3333-3333-3333-333333333332', '22222222-2222-2222-2222-222222222221', 'Rohan Mehta', 'advisor'),
    ('33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222221', 'Priya Sharma', 'team_leader'),
    ('33333333-3333-3333-3333-333333333334', '22222222-2222-2222-2222-222222222222', 'Arjun Patel', 'advisor'),
    ('33333333-3333-3333-3333-333333333335', '22222222-2222-2222-2222-222222222222', 'Neha Gupta', 'team_leader'),
    ('33333333-3333-3333-3333-333333333336', NULL, 'Vikram Singh', 'director');

-- === INDEXES ===

CREATE INDEX idx_calls_org ON calls(organization_id);
CREATE INDEX idx_calls_advisor ON calls(advisor_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_created ON calls(created_at DESC);
CREATE UNIQUE INDEX idx_calls_org_file_sha256 ON calls(organization_id, file_sha256) WHERE file_sha256 IS NOT NULL;
CREATE UNIQUE INDEX idx_calls_ingestion_fingerprint ON calls(ingestion_fingerprint) WHERE ingestion_fingerprint IS NOT NULL;
CREATE INDEX idx_flag_reviews_call ON flag_reviews(call_id);
CREATE INDEX idx_flag_reviews_flag_id ON flag_reviews(flag_id);
CREATE INDEX idx_flag_reviews_status ON flag_reviews(status);
