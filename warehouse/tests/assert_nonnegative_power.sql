
SELECT
    measured_at,
    site_id,
    panel_id,
    power_w

FROM {{ ref('stg_solar_readings') }}

WHERE power_w < 0