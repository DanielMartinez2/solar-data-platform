
SELECT
    site_id,
    panel_id,
    min_power_w,
    avg_power_w,
    max_power_w

FROM {{ ref('mart_panel_performance') }}

WHERE
    min_power_w < 0
    OR min_power_w > avg_power_w
    OR avg_power_w > max_power_w