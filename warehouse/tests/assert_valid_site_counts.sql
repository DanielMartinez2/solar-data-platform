
SELECT
    site_id,
    panel_count,
    reading_count

FROM {{ ref('mart_site_performance') }}

WHERE
    panel_count <= 0
    OR reading_count <= 0
    OR panel_count > reading_count