-- === Task 13: Vendor Retries and Recovery ===
-- Adds failed_stage column to capture which pipeline stage failed.

ALTER TABLE calls ADD COLUMN IF NOT EXISTS failed_stage TEXT;
