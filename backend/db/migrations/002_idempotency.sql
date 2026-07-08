-- === Task 12: Idempotent Call Processing ===
-- Adds columns + unique index for file-hash based idempotency.

ALTER TABLE calls ADD COLUMN IF NOT EXISTS file_sha256 TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'FILE_UPLOAD';
ALTER TABLE calls ADD COLUMN IF NOT EXISTS external_call_id TEXT;

-- Update status CHECK to include CANCELLED
ALTER TABLE calls DROP CONSTRAINT IF EXISTS calls_status_check;
ALTER TABLE calls ADD CONSTRAINT calls_status_check
    CHECK (status IN ('uploaded', 'processing', 'completed', 'failed', 'cancelled'));

-- Unique index enforces idempotency at the database level
CREATE UNIQUE INDEX IF NOT EXISTS idx_calls_org_file_sha256
    ON calls(organization_id, file_sha256) WHERE file_sha256 IS NOT NULL;

-- Backfill source for existing upload rows
UPDATE calls SET source = 'FILE_UPLOAD' WHERE source IS NULL;
