
SELECT
    site_id,
    measured_at,
    COUNT(*) AS total

FROM {{ ref('mart_site_power_timeseries') }}

GROUP BY
    site_id,
    measured_at

HAVING COUNT(*) > 1