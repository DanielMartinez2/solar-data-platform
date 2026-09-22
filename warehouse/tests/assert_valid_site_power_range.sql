
SELECT
    site_id,
    min_panel_reading_power_w,
    avg_panel_reading_power_w,
    max_panel_reading_power_w

FROM {{ ref('mart_site_performance') }}

WHERE
    min_panel_reading_power_w < 0
    OR min_panel_reading_power_w > avg_panel_reading_power_w
    OR avg_panel_reading_power_w > max_panel_reading_power_w