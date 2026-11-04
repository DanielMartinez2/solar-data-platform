-- Operational quality metrics for each ingestion attempt.
-- Counts come from immutable audit records; no duplicate storage is needed.
-- Incomplete/failed runs have NULL metrics rather than misleading 0% rates.
CREATE VIEW vw_ingestion_batch_quality AS
SELECT
    r.id AS ingestion_run_id,
    r.source_file,
    r.status,
    r.started_at,
    r.finished_at,
    p.processed_at,
    CASE WHEN r.status = 'success'
        THEN r.accepted_count + r.quarantined_count + r.duplicate_count
    END AS total_source_rows,
    CASE WHEN r.status = 'success' THEN r.accepted_count END AS accepted_count,
    CASE WHEN r.status = 'success' THEN r.quarantined_count END AS quarantined_count,
    CASE WHEN r.status = 'success' THEN r.duplicate_count END AS duplicate_count,
    CASE WHEN r.status = 'success' THEN r.inserted_readings_count END AS inserted_readings_count,
    CASE WHEN r.status = 'success' THEN r.inserted_quarantined_count END AS inserted_quarantined_count,
    CASE WHEN r.status = 'success' THEN
        ROUND(
            100.0 * r.quarantined_count /
            NULLIF(r.accepted_count + r.quarantined_count, 0),
            2
        )
    END AS quarantine_rate_pct,
    CASE WHEN r.status = 'success' THEN
        ROUND(
            100.0 * r.duplicate_count /
            NULLIF(r.accepted_count + r.quarantined_count + r.duplicate_count, 0),
            2
        )
    END AS duplicate_rate_pct,
    CASE WHEN r.status = 'success' THEN
        ROUND(
            100.0 * r.inserted_readings_count /
            NULLIF(r.accepted_count, 0),
            2
        )
    END AS insertion_rate_pct,
    r.error_message
FROM ingestion_runs AS r
LEFT JOIN processed_files AS p
    ON p.ingestion_run_id = r.id;
