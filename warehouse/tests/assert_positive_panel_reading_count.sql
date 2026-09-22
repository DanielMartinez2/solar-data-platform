
SELECT
    site_id,
    panel_id,
    reading_count

FROM {{ ref('mart_panel_performance') }}

WHERE reading_count <= 0