
SELECT
    site_id,

    DATE_TRUNC(
        'hour',
        measured_at,
        'UTC'
    ) AS hour_utc,

    COUNT(*) AS measurement_count,

    ROUND(
        AVG(observed_power_w)::numeric,
        2
    ) AS avg_observed_power_w,

    ROUND(
        MAX(observed_power_w)::numeric,
        2
    ) AS max_observed_power_w

FROM {{ ref('mart_site_power_timeseries') }}

GROUP BY
    site_id,
    DATE_TRUNC('hour', measured_at, 'UTC')