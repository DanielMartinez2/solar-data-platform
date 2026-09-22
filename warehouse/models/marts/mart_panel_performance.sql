
SELECT
    site_id,
    panel_id,

    COUNT(*) AS reading_count,

    MIN(measured_at) AS first_measured_at,
    MAX(measured_at) AS last_measured_at,

    ROUND(AVG(power_w)::numeric, 2) AS avg_power_w,
    ROUND(MIN(power_w)::numeric, 2) AS min_power_w,
    ROUND(MAX(power_w)::numeric, 2) AS max_power_w

FROM {{ ref('stg_solar_readings') }}

GROUP BY
    site_id,
    panel_id