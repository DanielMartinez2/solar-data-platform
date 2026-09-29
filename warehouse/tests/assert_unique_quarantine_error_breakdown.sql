SELECT
    site_id,
    day_local,
    error_type,
    error_column,
    COUNT(*) AS total

FROM {{ ref('mart_quarantine_error_breakdown') }}

GROUP BY
    site_id,
    day_local,
    error_type,
    error_column

HAVING COUNT(*) > 1