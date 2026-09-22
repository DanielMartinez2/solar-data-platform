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