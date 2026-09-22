
CREATE TABLE ingestion_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_file VARCHAR(255) NOT NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'failed')),

    accepted_count INTEGER NOT NULL DEFAULT 0
        CHECK (accepted_count >= 0),

    inserted_readings_count INTEGER NOT NULL DEFAULT 0
        CHECK (inserted_readings_count >= 0),

    quarantined_count INTEGER NOT NULL DEFAULT 0
        CHECK (quarantined_count >= 0),

    inserted_quarantined_count INTEGER NOT NULL DEFAULT 0
        CHECK (inserted_quarantined_count >= 0),

    duplicate_count INTEGER NOT NULL DEFAULT 0
        CHECK (duplicate_count >= 0),

    error_message TEXT,

    CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR
        (status IN ('success', 'failed') AND finished_at IS NOT NULL)
    )
);