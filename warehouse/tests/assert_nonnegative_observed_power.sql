
SELECT
    site_id,
    measured_at,
    observed_power_w

FROM {{ ref('mart_site_power_timeseries') }}

WHERE observed_power_w < 0