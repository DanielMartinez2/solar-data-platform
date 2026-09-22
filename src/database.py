import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

import psycopg
from psycopg.types.json import Jsonb

from src.validate_readings import (
    AcceptedReading,
    IngestionResult,
    QuarantinedReading,
    process_csv,
)

load_dotenv()

INSERT_READING_SQL = """
    INSERT INTO solar_readings (
        timestamp,
        site_id,
        panel_id,
        irradiance_wm2,
        temperature_c,
        voltage_v,
        current_a
    )
    VALUES (
        %s,
        %s,
        %s,
        %s,
        %s,
        %s,
        %s
    )
    ON CONFLICT (timestamp, site_id, panel_id)
    DO NOTHING;
"""
INSERT_QUARANTINE_SQL = """
    INSERT INTO quarantined_readings (
        source_file,
        source_row,
        raw_record,
        errors
    )
    VALUES (
        %s,
        %s,
        %s,
        %s
    )
    ON CONFLICT (source_file, source_row)
    DO NOTHING;
"""

def get_connection() -> psycopg.Connection[Any]:
    database_url = os.environ["DATABASE_URL"]

    return psycopg.connect(database_url)



def insert_readings(
    readings: list[AcceptedReading],
    *,
    connection: psycopg.Connection[Any] | None = None,
) -> int:
    if connection is None:
        with get_connection() as own_connection:
            return insert_readings(
                readings,
                connection=own_connection,
            )

    inserted_count = 0

    with connection.cursor() as cursor:
        for reading in readings:
            cursor.execute(
                INSERT_READING_SQL,
                (
                    reading["timestamp"],
                    reading["site_id"],
                    reading["panel_id"],
                    reading["irradiance_wm2"],
                    reading["temperature_c"],
                    reading["voltage_v"],
                    reading["current_a"],
                ),
            )

            inserted_count += cursor.rowcount

    return inserted_count


def insert_quarantined_readings(
    source_file: str,
    readings: list[QuarantinedReading],
    *,
    connection: psycopg.Connection[Any] | None = None,
) -> int:
    if connection is None:
        with get_connection() as own_connection:
            return insert_quarantined_readings(
                source_file,
                readings,
                connection=own_connection,
            )

    inserted_count = 0

    with connection.cursor() as cursor:
        for reading in readings:
            cursor.execute(
                INSERT_QUARANTINE_SQL,
                (
                    source_file,
                    reading["row"],
                    Jsonb(reading["record"]),
                    Jsonb(reading["errors"]),
                ),
            )

            inserted_count += cursor.rowcount

    return inserted_count


def start_ingestion_run(source_file: str) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ingestion_runs (source_file)
                VALUES (%s)
                RETURNING id;
                """,
                (source_file,),
            )

            result = cursor.fetchone()

            assert result is not None
            return int(result[0])


def finish_ingestion_run_success(
    run_id: int,
    result: IngestionResult,
    inserted_readings: int,
    inserted_quarantined: int,
    *,
    connection: psycopg.Connection[Any],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE ingestion_runs
            SET
                status = 'success',
                finished_at = NOW(),
                accepted_count = %s,
                inserted_readings_count = %s,
                quarantined_count = %s,
                inserted_quarantined_count = %s,
                duplicate_count = %s,
                error_message = NULL
            WHERE id = %s
              AND status = 'running'
            RETURNING id;
            """,
            (
                len(result["accepted"]),
                inserted_readings,
                len(result["quarantined"]),
                inserted_quarantined,
                len(result["skipped_duplicate_rows"]),
                run_id,
            ),
        )

        if cursor.fetchone() is None:
            raise ValueError(
                f"Ingestion run {run_id} does not exist "
                "or is not running"
            )


def finish_ingestion_run_failed(
    run_id: int,
    error_message: str,
) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ingestion_runs
                SET
                    status = 'failed',
                    finished_at = NOW(),
                    error_message = %s
                WHERE id = %s
                  AND status = 'running'
                RETURNING id;
                """,
                (
                    error_message,
                    run_id,
                ),
            )

            if cursor.fetchone() is None:
                raise ValueError(
                    f"Ingestion run {run_id} does not exist "
                    "or is not running"
                )

def ingest_csv(
    csv_path: Path,
) -> tuple[IngestionResult, int, int]:
    run_id = start_ingestion_run(csv_path.name)

    try:
        result = process_csv(csv_path)

        with get_connection() as connection:
            inserted_readings = insert_readings(
                result["accepted"],
                connection=connection,
            )

            inserted_quarantined = insert_quarantined_readings(
                csv_path.name,
                result["quarantined"],
                connection=connection,
            )

            finish_ingestion_run_success(
                run_id,
                result,
                inserted_readings,
                inserted_quarantined,
                connection=connection,
            )

    except Exception as error:
        finish_ingestion_run_failed(
            run_id,
            str(error),
        )
        raise

    return (
        result,
        inserted_readings,
        inserted_quarantined,
    )

def main() -> None:
    csv_path = (
        Path(__file__).parents[1]
        / "data/raw/solar_readings.csv"
    )

    result, inserted_readings, inserted_quarantined = (
        ingest_csv(csv_path)
    )

    print(
        "Accepted readings:",
        len(result["accepted"]),
    )
    print(
        "Inserted readings:",
        inserted_readings,
    )
    print(
        "Quarantined readings:",
        len(result["quarantined"]),
    )
    print(
        "Inserted quarantined readings:",
        inserted_quarantined,
    )
    print(
        "Skipped source duplicates:",
        result["skipped_duplicate_rows"],
    )


if __name__ == "__main__":
    main()