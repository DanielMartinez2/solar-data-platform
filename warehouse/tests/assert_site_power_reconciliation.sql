
WITH expected AS (
    SELECT
        site_id,
        measured_at,
        COUNT(DISTINCT panel_id) AS expected_panel_count,
        ROUND(
            SUM(power_w)::numeric, 2
        ) AS expected_power_w

    FROM {{ ref('stg_solar_readings') }}

    GROUP BY
        site_id,
        measured_at
),

actual AS (
    SELECT
        site_id,
        measured_at,
        reporting_panel_count,
        observed_power_w

    FROM {{ ref('mart_site_power_timeseries') }}
)

SELECT
    COALESCE(e.site_id, a.site_id) AS site_id,
    COALESCE(e.measured_at, a.measured_at) AS measured_at,

    e.expected_panel_count,
    a.reporting_panel_count,

    e.expected_power_w,
    a.observed_power_w

FROM expected AS e

FULL OUTER JOIN actual AS a
    ON e.site_id = a.site_id
    AND e.measured_at = a.measured_at

WHERE
    e.site_id IS NULL
    OR a.site_id IS NULL
    OR e.expected_panel_count
        IS DISTINCT FROM a.reporting_panel_count
    OR e.expected_power_w
        IS DISTINCT FROM a.observed_power_w