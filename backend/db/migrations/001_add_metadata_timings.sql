-- Add metadata and timings columns to the transcripts table
ALTER TABLE transcripts
ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS timings JSONB NOT NULL DEFAULT '{}'::jsonb;
