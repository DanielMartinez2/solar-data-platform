-- A completed checkpoint is immutable: the same source name cannot be reused
-- with different bytes without explicitly handling the source correction.
CREATE TABLE processed_files (
    source_file VARCHAR(255) PRIMARY KEY,
    sha256 CHAR(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    ingestion_run_id BIGINT NOT NULL REFERENCES ingestion_runs(id),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
