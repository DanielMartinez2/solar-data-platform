
SELECT
    site_id,
    hour_utc,
    measurement_count

FROM {{ ref('mart_site_hourly_power') }}

WHERE measurement_count <= 0