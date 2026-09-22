
SELECT
    site_id,

    COUNT(DISTINCT panel_id) AS panel_count,
    COUNT(*) AS reading_count,

    MIN(measured_at) AS first_measured_at,
    MAX(measured_at) AS last_measured_at,

    ROUND(
        AVG(power_w)::numeric, 2
    ) AS avg_panel_reading_power_w,

    ROUND(
        MIN(power_w)::numeric, 2
    ) AS min_panel_reading_power_w,

    ROUND(
        MAX(power_w)::numeric, 2
    ) AS max_panel_reading_power_w

FROM {{ ref('stg_solar_readings') }}

GROUP BY
    site_id