
SELECT
    site_id,
    measured_at,

    COUNT(DISTINCT panel_id) AS reporting_panel_count,

    ROUND(
        SUM(power_w)::numeric, 2
    ) AS observed_power_w

FROM {{ ref('stg_solar_readings') }}

GROUP BY
    site_id,
    measured_at