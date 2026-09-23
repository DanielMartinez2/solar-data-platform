
WITH expected AS (
    SELECT
        site_id,

        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date AS day_local,

        COUNT(*) AS measurement_count,

        SUM(reporting_panel_count)
            AS reported_panel_readings,

        ROUND(
            AVG(observed_power_w)::numeric,
            2
        ) AS avg_observed_power_w,

        ROUND(
            MAX(observed_power_w)::numeric,
            2
        ) AS max_observed_power_w

    FROM {{ ref('mart_site_power_timeseries') }}

    GROUP BY
        site_id,
        (
            (measured_at AT TIME ZONE 'UTC')
            - INTERVAL '3 hours'
        )::date
),

actual AS (
    SELECT
        site_id,
        day_local,
        measurement_count,
        reported_panel_readings,
        avg_observed_power_w,
        max_observed_power_w

    FROM {{ ref('mart_site_daily_power') }}
)

SELECT
    COALESCE(e.site_id, a.site_id) AS site_id,
    COALESCE(e.day_local, a.day_local) AS day_local,

    e.measurement_count AS expected_measurements,
    a.measurement_count AS actual_measurements,

    e.reported_panel_readings AS expected_panel_readings,
    a.reported_panel_readings AS actual_panel_readings,

    e.avg_observed_power_w AS expected_avg_power_w,
    a.avg_observed_power_w AS actual_avg_power_w,

    e.max_observed_power_w AS expected_max_power_w,
    a.max_observed_power_w AS actual_max_power_w

FROM expected AS e

FULL OUTER JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.day_local = a.day_local

WHERE
    e.site_id IS NULL
    OR a.site_id IS NULL

    OR e.measurement_count
        IS DISTINCT FROM a.measurement_count

    OR e.reported_panel_readings
        IS DISTINCT FROM a.reported_panel_readings

    OR e.avg_observed_power_w
        IS DISTINCT FROM a.avg_observed_power_w

    OR e.max_observed_power_w
        IS DISTINCT FROM a.max_observed_power_w