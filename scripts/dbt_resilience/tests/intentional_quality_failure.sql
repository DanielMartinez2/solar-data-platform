-- A singular dbt test fails if this query returns one or more rows.
-- No project models or tables are modified.
select 1 as failing_row
where {{ "true" if env_var('DBT_RESILIENCE_FORCE_FAILURE', 'true') == 'true' else "false" }}
