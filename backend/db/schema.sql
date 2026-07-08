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
    duration_sec FLOAT,
    language TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
    error_message TEXT,
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
    ('00000000-0000-0000-0000-000000000001', 'FitNova');

INSERT INTO teams (id, organization_id, name) VALUES
    ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'Pod Alpha'),
    ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'Pod Beta');

INSERT INTO advisors (id, team_id, name, role) VALUES
    ('00000000-0000-0000-0000-000000000100', '00000000-0000-0000-0000-000000000010', 'Saad Khan', 'advisor'),
    ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000010', 'Rohan Mehta', 'advisor'),
    ('00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000010', 'Priya Sharma', 'team_leader'),
    ('00000000-0000-0000-0000-000000000103', '00000000-0000-0000-0000-000000000011', 'Arjun Patel', 'advisor'),
    ('00000000-0000-0000-0000-000000000104', '00000000-0000-0000-0000-000000000011', 'Neha Gupta', 'team_leader'),
    ('00000000-0000-0000-0000-000000000105', NULL, 'Vikram Singh', 'director');

-- === INDEXES ===

CREATE INDEX idx_calls_org ON calls(organization_id);
CREATE INDEX idx_calls_advisor ON calls(advisor_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_created ON calls(created_at DESC);
CREATE INDEX idx_flag_reviews_call ON flag_reviews(call_id);
CREATE INDEX idx_flag_reviews_flag_id ON flag_reviews(flag_id);
CREATE INDEX idx_flag_reviews_status ON flag_reviews(status);
