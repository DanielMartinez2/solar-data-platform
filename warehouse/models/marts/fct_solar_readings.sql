
SELECT
    measured_at,
    site_id,
    panel_id,

    irradiance_wm2,
    temperature_c,
    voltage_v,
    current_a,
    power_w,

    ingested_at

FROM {{ ref('stg_solar_readings') }}