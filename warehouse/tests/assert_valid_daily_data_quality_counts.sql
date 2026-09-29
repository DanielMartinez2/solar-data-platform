SELECT
    site_id,
    day_local,
    expected_panel_readings,
    valid_panel_readings,
    missing_or_rejected_readings,
    rejected_measurements,
    invalid_measurements,
    conflict_measurements,
    gap_measurements

FROM {{ ref('mart_site_daily_data_quality') }}

WHERE
    expected_panel_readings < 0
    OR valid_panel_readings < 0
    OR missing_or_rejected_readings < 0
    OR rejected_measurements < 0
    OR invalid_measurements < 0
    OR conflict_measurements < 0
    OR gap_measurements < 0

    OR valid_panel_readings
        + missing_or_rejected_readings
        <> expected_panel_readings

    OR rejected_measurements
        <> invalid_measurements + conflict_measurements

    OR missing_or_rejected_readings
        <> gap_measurements + rejected_measurements