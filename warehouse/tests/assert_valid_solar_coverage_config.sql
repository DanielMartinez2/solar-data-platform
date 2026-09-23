
SELECT
    site_id,
    start_date,
    end_date,
    expected_panel_count,
    interval_minutes

FROM {{ ref('solar_coverage_config') }}

WHERE
    start_date::date > end_date::date
    OR expected_panel_count::integer <= 0
    OR interval_minutes::integer <= 0
    OR 1440 % NULLIF(interval_minutes::integer, 0) <> 0