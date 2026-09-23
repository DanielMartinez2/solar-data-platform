
SELECT
    site_id,
    day_local,
    avg_observed_power_w,
    max_observed_power_w

FROM {{ ref('mart_site_daily_power') }}

WHERE
    avg_observed_power_w < 0
    OR max_observed_power_w < 0
    OR avg_observed_power_w > max_observed_power_w