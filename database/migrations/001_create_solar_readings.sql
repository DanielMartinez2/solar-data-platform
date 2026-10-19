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
