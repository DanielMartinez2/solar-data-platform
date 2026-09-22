SELECT
    timestamp AS measured_at,
    site_id,
    panel_id,
    irradiance_wm2,
    temperature_c,
    voltage_v,
    current_a,
    voltage_v * current_a AS power_w,
    ingested_at

FROM {{ source('solar_raw', 'solar_readings') }}