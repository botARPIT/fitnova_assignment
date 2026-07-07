-- Migration 001: Replace flag_reviews table with UUID-based design
-- 
-- Changes:
--   - flag_index INT → flag_id UUID (stable identifier per flag)
--   - reviewer_id → split into advisor_id (contestor) + team_leader_id (resolver)
--   - decision → replaced with status + resolved_at workflow
--   - reviewed_at → created_at + resolved_at
--   - reason → split into contest_reason + decision_reason

DROP TABLE IF EXISTS flag_reviews;

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

CREATE INDEX idx_flag_reviews_call ON flag_reviews(call_id);
CREATE INDEX idx_flag_reviews_flag_id ON flag_reviews(flag_id);
CREATE INDEX idx_flag_reviews_status ON flag_reviews(status);
