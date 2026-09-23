
SELECT
    site_id,
    day_local,
    expected_panel_count,
    expected_slots,
    expected_panel_readings,
    valid_panel_readings,
    missing_or_rejected_readings

FROM {{ ref('mart_site_daily_coverage') }}

WHERE
    expected_panel_count <= 0

    OR expected_slots <= 0

    OR expected_panel_readings
        <> expected_panel_count * expected_slots

    OR valid_panel_readings < 0

    OR valid_panel_readings > expected_panel_readings

    OR missing_or_rejected_readings
        <> expected_panel_readings - valid_panel_readings