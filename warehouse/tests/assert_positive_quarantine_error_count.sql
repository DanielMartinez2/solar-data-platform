SELECT
    site_id,
    day_local,
    error_type,
    error_column,
    error_count

FROM {{ ref('mart_quarantine_error_breakdown') }}

WHERE error_count <= 0