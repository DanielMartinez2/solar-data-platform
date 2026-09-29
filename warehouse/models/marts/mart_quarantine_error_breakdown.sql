WITH exploded_errors AS (
    SELECT
        (q.raw_record ->> 'timestamp')::timestamptz AS measured_at,
        q.raw_record ->> 'site_id' AS site_id,
        q.raw_record ->> 'panel_id' AS panel_id,

        error ->> 'type' AS error_type,
        error ->> 'column' AS error_column

    FROM {{ source('solar_raw', 'quarantined_readings') }} AS q

    CROSS JOIN LATERAL jsonb_array_elements(q.errors) AS error

    WHERE
        q.raw_record ? 'timestamp'
        AND q.raw_record ? 'site_id'
        AND q.raw_record ? 'panel_id'
),

validation_errors AS (
    SELECT
        measured_at,
        site_id,
        panel_id,
        error_type,
        error_column

    FROM exploded_errors

    WHERE error_type <> 'conflict'
)

SELECT
    site_id,

    (
        (measured_at AT TIME ZONE 'UTC')
        - INTERVAL '3 hours'
    )::date AS day_local,

    error_type,
    error_column,

    COUNT(*) AS error_count

FROM validation_errors

GROUP BY
    site_id,
    (
        (measured_at AT TIME ZONE 'UTC')
        - INTERVAL '3 hours'
    )::date,
    error_type,
    error_column