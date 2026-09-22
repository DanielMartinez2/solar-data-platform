
SELECT
    site_id,
    COUNT(*) AS total

FROM {{ ref('mart_site_performance') }}

GROUP BY site_id

HAVING COUNT(*) > 1