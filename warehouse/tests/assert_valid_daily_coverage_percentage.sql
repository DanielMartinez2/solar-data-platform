
SELECT
    site_id,
    day_local,
    coverage_pct

FROM {{ ref('mart_site_daily_coverage') }}

WHERE
    coverage_pct < 0

    OR coverage_pct > 100

    OR coverage_pct IS DISTINCT FROM
        ROUND(
            100.0 * valid_panel_readings
            / NULLIF(expected_panel_readings, 0),
            2
        )