
SELECT
    site_id,
    hour_utc,
    COUNT(*) AS total

FROM {{ ref('mart_site_hourly_power') }}

GROUP BY
    site_id,
    hour_utc

HAVING COUNT(*) > 1