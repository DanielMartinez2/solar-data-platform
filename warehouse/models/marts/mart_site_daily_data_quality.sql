WITH quarantined_rows AS (
    SELECT
        (raw_record ->> 'timestamp')::timestamptz
            AS measured_at,

        raw_record ->> 'site_id'
            AS site_id,

        raw_record ->> 'panel_id'
            AS panel_id,

        EXISTS (
            SELECT 1
            FROM jsonb_array_elements(errors) AS error
            WHERE error ->> 'type' = 'conflict'
        ) AS has_conflict

    FROM {{ source('solar_raw', 'quarantined_readings') }}

    WHERE
        raw_record ? 'timestamp'
        AND raw_record ? 'site_id'
        AND raw_record ? 'panel_id'
),

quarantined_natural_keys AS (
    SELECT
        measured_at,
        site_id,
        panel_id,

        BOOL_OR(has_conflict)
            AS has_conflict

    FROM quarantined_rows

    GROUP BY
        measured_at,
        site_id,
        panel_id
),

unresolved_rejected AS (
    SELECT
        q.measured_at,
        q.site_id,
        q.panel_id,
        q.has_conflict

    FROM quarantined_natural_keys AS q

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
)

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