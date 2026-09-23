
SELECT
    site_id,
    day_local,
    COUNT(*) AS total

FROM {{ ref('mart_site_daily_power') }}

GROUP BY
    site_id,
    day_local

HAVING COUNT(*) > 1