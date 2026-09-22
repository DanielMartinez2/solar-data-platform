
SELECT
    site_id,
    panel_id,
    COUNT(*) AS total

FROM {{ ref('mart_panel_performance') }}

GROUP BY
    site_id,
    panel_id

HAVING COUNT(*) > 1