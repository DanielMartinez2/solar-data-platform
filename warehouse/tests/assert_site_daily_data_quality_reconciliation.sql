WITH quarantined_keys AS (
    SELECT
        (raw_record ->> 'timestamp')::timestamptz AS measured_at,
        raw_record ->> 'site_id' AS site_id,
        raw_record ->> 'panel_id' AS panel_id,

        BOOL_OR(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(errors) AS error
                WHERE error ->> 'type' = 'conflict'
            )
        ) AS has_conflict

    FROM {{ source('solar_raw', 'quarantined_readings') }}

    WHERE
        raw_record ? 'timestamp'
        AND raw_record ? 'site_id'
        AND raw_record ? 'panel_id'

    GROUP BY
        (raw_record ->> 'timestamp')::timestamptz,
        raw_record ->> 'site_id',
        raw_record ->> 'panel_id'
),

unresolved_rejected AS (
    SELECT
        q.measured_at,
        q.site_id,
        q.panel_id,
        q.has_conflict

    FROM quarantined_keys AS q

    LEFT JOIN {{ ref('fct_solar_readings') }} AS f
        ON q.measured_at = f.measured_at
        AND q.site_id = f.site_id
        AND q.panel_id = f.panel_id

    WHERE f.measured_at IS NULL
),

rejected_by_day AS (
    SELECT
        site_id,

        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date AS day_local,

        COUNT(*) AS rejected_measurements,

        COUNT(*) FILTER (
            WHERE NOT has_conflict
        ) AS invalid_measurements,

        COUNT(*) FILTER (
            WHERE has_conflict
        ) AS conflict_measurements

    FROM unresolved_rejected

    GROUP BY
        site_id,
        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date
),

expected AS (
    SELECT
        c.site_id,
        c.day_local,
        c.expected_panel_readings,
        c.valid_panel_readings,
        c.missing_or_rejected_readings,

        COALESCE(r.rejected_measurements, 0)
            AS rejected_measurements,

        COALESCE(r.invalid_measurements, 0)
            AS invalid_measurements,

        COALESCE(r.conflict_measurements, 0)
            AS conflict_measurements,

        c.missing_or_rejected_readings
            - COALESCE(r.rejected_measurements, 0)
            AS gap_measurements

    FROM {{ ref('mart_site_daily_coverage') }} AS c

    LEFT JOIN rejected_by_day AS r
        ON c.site_id = r.site_id
        AND c.day_local = r.day_local
),

actual AS (
    SELECT *
    FROM {{ ref('mart_site_daily_data_quality') }}
)

SELECT
    COALESCE(e.site_id, a.site_id) AS site_id,
    COALESCE(e.day_local, a.day_local) AS day_local,

    e.gap_measurements AS expected_gaps,
    a.gap_measurements AS actual_gaps,

    e.invalid_measurements AS expected_invalid,
    a.invalid_measurements AS actual_invalid,

    e.conflict_measurements AS expected_conflicts,
    a.conflict_measurements AS actual_conflicts

FROM expected AS e

FULL OUTER JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.day_local = a.day_local

WHERE
    e.site_id IS NULL
    OR a.site_id IS NULL

    OR e.expected_panel_readings
        IS DISTINCT FROM a.expected_panel_readings

    OR e.valid_panel_readings
        IS DISTINCT FROM a.valid_panel_readings

    OR e.missing_or_rejected_readings
        IS DISTINCT FROM a.missing_or_rejected_readings

    OR e.rejected_measurements
        IS DISTINCT FROM a.rejected_measurements

    OR e.invalid_measurements
        IS DISTINCT FROM a.invalid_measurements

    OR e.conflict_measurements
        IS DISTINCT FROM a.conflict_measurements

    OR e.gap_measurements
        IS DISTINCT FROM a.gap_measurements