
SELECT
    site_id,
    hour_utc,
    avg_observed_power_w,
    max_observed_power_w

FROM {{ ref('mart_site_hourly_power') }}

WHERE
    avg_observed_power_w < 0
    OR max_observed_power_w < 0
    OR avg_observed_power_w > max_observed_power_w