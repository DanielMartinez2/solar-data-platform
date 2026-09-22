
SELECT
    f.measured_at,
    f.site_id,
    f.panel_id

FROM {{ ref('fct_solar_readings') }} AS f

LEFT JOIN {{ ref('dim_panels') }} AS d
    ON f.site_id = d.site_id
    AND f.panel_id = d.panel_id

WHERE d.site_id IS NULL