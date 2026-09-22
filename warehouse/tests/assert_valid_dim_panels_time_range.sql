
SELECT
    site_id,
    panel_id,
    first_seen_at,
    last_seen_at

FROM {{ ref('dim_panels') }}

WHERE first_seen_at > last_seen_at