
WITH ordered AS (
    SELECT
        site_id,
        start_date::date AS start_date,
        end_date::date AS end_date,

        MAX(end_date::date) OVER (
            PARTITION BY site_id
            ORDER BY
                start_date::date,
                end_date::date DESC
            ROWS BETWEEN UNBOUNDED PRECEDING
                AND 1 PRECEDING
        ) AS previous_max_end_date

    FROM {{ ref('solar_coverage_config') }}
)

SELECT
    site_id,
    start_date,
    end_date,
    previous_max_end_date

FROM ordered

WHERE previous_max_end_date >= start_date