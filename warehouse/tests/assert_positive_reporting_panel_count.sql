
SELECT
    site_id,
    measured_at,
    reporting_panel_count

FROM {{ ref('mart_site_power_timeseries') }}

WHERE reporting_panel_count <= 0