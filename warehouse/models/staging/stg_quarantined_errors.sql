SELECT
    q.source_file,
    q.source_row,

    (q.raw_record ->> 'timestamp')::timestamptz
        AS measured_at,

    q.raw_record ->> 'site_id'
        AS site_id,

    q.raw_record ->> 'panel_id'
        AS panel_id,

    error ->> 'type'
        AS error_type,

    error ->> 'column'
        AS error_column,

    error ->> 'invalid_value'
        AS invalid_value,

    CASE
        WHEN error ? 'related_row'
        THEN (error ->> 'related_row')::integer
    END AS related_row

FROM {{ source('solar_raw', 'quarantined_readings') }} AS q

CROSS JOIN LATERAL
    jsonb_array_elements(q.errors) AS error