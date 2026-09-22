import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

import psycopg
from psycopg.types.json import Jsonb

from src.validate_readings import (
    AcceptedReading,
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
) -> int:

    inserted_count = 0

    with get_connection() as connection:
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
) -> int:

    inserted_count = 0

    with get_connection() as connection:
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

def main():
    csv_path = (
        Path(__file__).parents[1]
        / "data/raw/solar_readings.csv"
    )

    result = process_csv(csv_path)

    inserted_readings = insert_readings(
        result["accepted"]
    )

    inserted_quarantined = insert_quarantined_readings(
        csv_path.name,
        result["quarantined"],
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