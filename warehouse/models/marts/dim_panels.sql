
SELECT
    site_id,
    panel_id,

    MIN(measured_at) AS first_seen_at,
    MAX(measured_at) AS last_seen_at

FROM {{ ref('stg_solar_readings') }}

GROUP BY
    site_id,
    panel_id