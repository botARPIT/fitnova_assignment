-- Add ingestion_fingerprint idempotency metadata and align schema with active pipeline.

ALTER TABLE calls ADD COLUMN IF NOT EXISTS ingestion_fingerprint TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS failed_stage TEXT;

UPDATE calls
SET ingestion_fingerprint = file_sha256
WHERE ingestion_fingerprint IS NULL
  AND file_sha256 IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_calls_ingestion_fingerprint
    ON calls(ingestion_fingerprint)
    WHERE ingestion_fingerprint IS NOT NULL;
