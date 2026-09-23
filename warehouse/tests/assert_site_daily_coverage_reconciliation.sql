
WITH expected_days AS (
    SELECT
        c.site_id,
        d.day_local::date AS day_local,

        c.expected_panel_count::integer
            AS expected_panel_count,

        1440 / c.interval_minutes::integer
            AS expected_slots,

        c.expected_panel_count::integer
            * (1440 / c.interval_minutes::integer)
            AS expected_panel_readings

    FROM {{ ref('solar_coverage_config') }} AS c

    CROSS JOIN LATERAL generate_series(
        c.start_date::date,
        c.end_date::date,
        INTERVAL '1 day'
    ) AS d(day_local)
),

valid_measurements AS (
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
),

expected AS (
    SELECT
        e.site_id,
        e.day_local,
        e.expected_panel_count,
        e.expected_slots,
        e.expected_panel_readings,

        COALESCE(v.valid_panel_readings, 0)
            AS valid_panel_readings,

        e.expected_panel_readings
            - COALESCE(v.valid_panel_readings, 0)
            AS missing_or_rejected_readings,

        ROUND(
            100.0 * COALESCE(v.valid_panel_readings, 0)
            / NULLIF(e.expected_panel_readings, 0),
            2
        ) AS coverage_pct

    FROM expected_days AS e

    LEFT JOIN valid_measurements AS v
        ON e.site_id = v.site_id
        AND e.day_local = v.day_local
),

actual AS (
    SELECT *
    FROM {{ ref('mart_site_daily_coverage') }}
)

SELECT
    COALESCE(e.site_id, a.site_id) AS site_id,
    COALESCE(e.day_local, a.day_local) AS day_local,

    e.valid_panel_readings AS expected_valid,
    a.valid_panel_readings AS actual_valid,

    e.coverage_pct AS expected_coverage,
    a.coverage_pct AS actual_coverage

FROM expected AS e

FULL OUTER JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.day_local = a.day_local

WHERE
    e.site_id IS NULL
    OR a.site_id IS NULL

    OR e.expected_panel_count
        IS DISTINCT FROM a.expected_panel_count

    OR e.expected_slots
        IS DISTINCT FROM a.expected_slots

    OR e.expected_panel_readings
        IS DISTINCT FROM a.expected_panel_readings

    OR e.valid_panel_readings
        IS DISTINCT FROM a.valid_panel_readings

    OR e.missing_or_rejected_readings
        IS DISTINCT FROM a.missing_or_rejected_readings

    OR e.coverage_pct
        IS DISTINCT FROM a.coverage_pct