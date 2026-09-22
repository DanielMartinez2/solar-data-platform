CREATE TABLE solar_readings (
    timestamp TIMESTAMPTZ NOT NULL,
    site_id VARCHAR(50) NOT NULL,
    panel_id VARCHAR(50) NOT NULL,

    irradiance_wm2 DOUBLE PRECISION NOT NULL
        CHECK (irradiance_wm2 >= 0),

    temperature_c DOUBLE PRECISION NOT NULL,

    voltage_v DOUBLE PRECISION NOT NULL
        CHECK (voltage_v >= 0),

    current_a DOUBLE PRECISION NOT NULL
        CHECK (current_a >= 0),

    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (timestamp, site_id, panel_id)
);

CREATE TABLE quarantined_readings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_file VARCHAR(255) NOT NULL,
    source_row INTEGER NOT NULL
        CHECK (source_row >= 2),

    raw_record JSONB NOT NULL
        CHECK (jsonb_typeof(raw_record) = 'object'),

    errors JSONB NOT NULL
        CHECK (
            jsonb_typeof(errors) = 'array'
            AND jsonb_array_length(errors) > 0
        ),

    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (source_file, source_row)
);


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