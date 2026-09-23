
WITH daily_readings AS (
    SELECT
        site_id,

        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date AS day_local,

        reporting_panel_count,
        observed_power_w

    FROM {{ ref('mart_site_power_timeseries') }}
)

SELECT
    site_id,
    day_local,

    COUNT(*) AS measurement_count,

    SUM(reporting_panel_count)
        AS reported_panel_readings,

    ROUND(
        AVG(observed_power_w)::numeric,
        2
    ) AS avg_observed_power_w,

    ROUND(
        MAX(observed_power_w)::numeric,
        2
    ) AS max_observed_power_w

FROM daily_readings

GROUP BY
    site_id,
    day_local