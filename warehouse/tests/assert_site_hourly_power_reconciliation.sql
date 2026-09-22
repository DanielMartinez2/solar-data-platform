
WITH expected AS (
    SELECT
        site_id,

        DATE_TRUNC(
            'hour',
            measured_at,
            'UTC'
        ) AS hour_utc,

        COUNT(*) AS expected_measurement_count,

        ROUND(
            AVG(observed_power_w)::numeric,
            2
        ) AS expected_avg_power_w,

        ROUND(
            MAX(observed_power_w)::numeric,
            2
        ) AS expected_max_power_w

    FROM {{ ref('mart_site_power_timeseries') }}

    GROUP BY
        site_id,
        DATE_TRUNC('hour', measured_at, 'UTC')
),

actual AS (
    SELECT
        site_id,
        hour_utc,
        measurement_count,
        avg_observed_power_w,
        max_observed_power_w

    FROM {{ ref('mart_site_hourly_power') }}
)

SELECT
    COALESCE(e.site_id, a.site_id) AS site_id,
    COALESCE(e.hour_utc, a.hour_utc) AS hour_utc,

    e.expected_measurement_count,
    a.measurement_count,

    e.expected_avg_power_w,
    a.avg_observed_power_w,

    e.expected_max_power_w,
    a.max_observed_power_w

FROM expected AS e

FULL OUTER JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.hour_utc = a.hour_utc

WHERE
    e.site_id IS NULL
    OR a.site_id IS NULL

    OR e.expected_measurement_count
        IS DISTINCT FROM a.measurement_count

    OR e.expected_avg_power_w
        IS DISTINCT FROM a.avg_observed_power_w

    OR e.expected_max_power_w
        IS DISTINCT FROM a.max_observed_power_w