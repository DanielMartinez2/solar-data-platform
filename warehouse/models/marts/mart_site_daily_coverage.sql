
WITH configuration AS (
    SELECT
        site_id,
        start_date::date AS start_date,
        end_date::date AS end_date,
        expected_panel_count::integer AS expected_panel_count,
        interval_minutes::integer AS interval_minutes

    FROM {{ ref('solar_coverage_config') }}
),

expected_days AS (
    SELECT
        c.site_id,
        d.day_local::date AS day_local,

        c.expected_panel_count,
        1440 / c.interval_minutes AS expected_slots,

        c.expected_panel_count
            * (1440 / c.interval_minutes)
            AS expected_panel_readings

    FROM configuration AS c

    CROSS JOIN LATERAL generate_series(
        c.start_date,
        c.end_date,
        INTERVAL '1 day'
    ) AS d(day_local)
),

actual AS (
    SELECT
        site_id,

        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date AS day_local,

        COUNT(*) AS valid_panel_readings

    FROM {{ ref('fct_solar_readings') }}

    GROUP BY
        site_id,
        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date
)

SELECT
    e.site_id,
    e.day_local,
    e.expected_panel_count,
    e.expected_slots,
    e.expected_panel_readings,

    COALESCE(a.valid_panel_readings, 0)
        AS valid_panel_readings,

    e.expected_panel_readings
        - COALESCE(a.valid_panel_readings, 0)
        AS missing_or_rejected_readings,

    ROUND(
        100.0 * COALESCE(a.valid_panel_readings, 0)
        / e.expected_panel_readings,
        2
    ) AS coverage_pct

FROM expected_days AS e

LEFT JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.day_local = a.day_local