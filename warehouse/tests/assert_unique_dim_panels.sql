
SELECT
    site_id,
    panel_id,
    COUNT(*) AS total

FROM {{ ref('dim_panels') }}

GROUP BY
    site_id,
    panel_id

HAVING COUNT(*) > 1