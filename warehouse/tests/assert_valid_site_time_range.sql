
SELECT
    site_id,
    first_measured_at,
    last_measured_at

FROM {{ ref('mart_site_performance') }}

WHERE first_measured_at > last_measured_at