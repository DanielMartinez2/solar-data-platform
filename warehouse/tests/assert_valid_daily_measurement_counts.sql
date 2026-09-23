
SELECT
    site_id,
    day_local,
    measurement_count,
    reported_panel_readings

FROM {{ ref('mart_site_daily_power') }}

WHERE
    measurement_count <= 0
    OR reported_panel_readings < measurement_count