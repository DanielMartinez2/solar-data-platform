WITH expected AS (
    SELECT
        q.raw_record ->> 'site_id' AS site_id,

        (
            (
                (q.raw_record ->> 'timestamp')::timestamptz
                AT TIME ZONE 'UTC'
            )
            - INTERVAL '3 hours'
        )::date AS day_local,

        error ->> 'type' AS error_type,
        error ->> 'column' AS error_column,

        COUNT(*) AS error_count

    FROM {{ source('solar_raw', 'quarantined_readings') }} AS q

    CROSS JOIN LATERAL
        jsonb_array_elements(q.errors) AS error

    WHERE
        q.raw_record ? 'timestamp'
        AND q.raw_record ? 'site_id'
        AND q.raw_record ? 'panel_id'
        AND error ->> 'type' <> 'conflict'

    GROUP BY
        q.raw_record ->> 'site_id',

        (
            (
                (q.raw_record ->> 'timestamp')::timestamptz
                AT TIME ZONE 'UTC'
            )
            - INTERVAL '3 hours'
        )::date,

        error ->> 'type',
        error ->> 'column'
),

actual AS (
    SELECT
        site_id,
        day_local,
        error_type,
        error_column,
        error_count

    FROM {{ ref('mart_quarantine_error_breakdown') }}
)

SELECT
    COALESCE(e.site_id, a.site_id) AS site_id,
    COALESCE(e.day_local, a.day_local) AS day_local,
    COALESCE(e.error_type, a.error_type) AS error_type,
    COALESCE(e.error_column, a.error_column) AS error_column,

    e.error_count AS expected_count,
    a.error_count AS actual_count

FROM expected AS e

FULL OUTER JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.day_local = a.day_local
    AND e.error_type = a.error_type
    AND e.error_column IS NOT DISTINCT FROM a.error_column

WHERE
    e.site_id IS NULL
    OR a.site_id IS NULL
    OR e.error_count IS DISTINCT FROM a.error_count