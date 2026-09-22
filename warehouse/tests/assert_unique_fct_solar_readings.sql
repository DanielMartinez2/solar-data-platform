
SELECT
    measured_at,
    site_id,
    panel_id,
    COUNT(*) AS total

FROM {{ ref('fct_solar_readings') }}

GROUP BY
    measured_at,
    site_id,
    panel_id

HAVING COUNT(*) > 1