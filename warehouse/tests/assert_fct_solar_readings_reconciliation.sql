
WITH staging AS (
    SELECT
        measured_at,
        site_id,
        panel_id,
        irradiance_wm2,
        temperature_c,
        voltage_v,
        current_a,
        power_w,
        ingested_at
    FROM {{ ref('stg_solar_readings') }}
),

facts AS (
    SELECT
        measured_at,
        site_id,
        panel_id,
        irradiance_wm2,
        temperature_c,
        voltage_v,
        current_a,
        power_w,
        ingested_at
    FROM {{ ref('fct_solar_readings') }}
),

missing_in_facts AS (
    SELECT * FROM staging
    EXCEPT ALL
    SELECT * FROM facts
),

unexpected_in_facts AS (
    SELECT * FROM facts
    EXCEPT ALL
    SELECT * FROM staging
)

SELECT
    'missing_in_facts' AS issue,
    *
FROM missing_in_facts

UNION ALL

SELECT
    'unexpected_in_facts' AS issue,
    *
FROM unexpected_in_facts