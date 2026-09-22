import os
from pathlib import Path

import pytest

from src.database import (
    get_connection,
    ingest_csv,
    insert_quarantined_readings,
    insert_readings,
)
from src.validate_readings import (
    IngestionResult,
    QuarantinedReading,
    process_csv,
)


TEST_SITE_ID = "PYTEST_E2E_SITE"
TEST_SOURCE_FILE = "pytest_e2e_pipeline.csv"



def delete_e2e_test_data() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM ingestion_runs
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )

            cursor.execute(
                """
                DELETE FROM solar_readings
                WHERE site_id = %s;
                """,
                (TEST_SITE_ID,),
            )

            cursor.execute(
                """
                DELETE FROM quarantined_readings
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )

@pytest.fixture(autouse=True)
def clean_database():
    if "DATABASE_URL" not in os.environ:
        pytest.skip(
            "DATABASE_URL is required for database integration tests"
        )

    delete_e2e_test_data()
    yield
    delete_e2e_test_data()


@pytest.fixture
def end_to_end_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / TEST_SOURCE_FILE
    csv_path.write_text(
        """timestamp,site_id,panel_id,irradiance_wm2,temperature_c,voltage_v,current_a
2099-01-01T12:00:00+00:00,PYTEST_E2E_SITE,PANEL_ACCEPTED_1,500.0,25.0,35.0,5.0
2099-01-01T12:00:00+00:00,PYTEST_E2E_SITE,PANEL_ACCEPTED_1,500.0,25.0,35.0,5.0
2099-01-01T12:05:00+00:00,PYTEST_E2E_SITE,PANEL_INVALID,510.0,,35.5,5.1
2099-01-01T12:10:00+00:00,PYTEST_E2E_SITE,PANEL_CONFLICT,520.0,26.0,36.0,5.2
2099-01-01T12:10:00+00:00,PYTEST_E2E_SITE,PANEL_CONFLICT,540.0,27.0,37.0,5.4
2099-01-01T12:10:00+00:00,PYTEST_E2E_SITE,PANEL_CONFLICT,540.0,27.0,37.0,5.4
2099-01-01T12:15:00+00:00,PYTEST_E2E_SITE,PANEL_ACCEPTED_2,550.0,28.0,38.0,5.5
""",
        encoding="utf-8",
    )
    return csv_path


def get_conflict_related_rows(
    reading: QuarantinedReading,
) -> set[int]:
    related_rows: set[int] = set()

    for error in reading["errors"]:
        if error["type"] != "conflict":
            continue

        related_row = error.get("related_row")
        assert related_row is not None
        related_rows.add(related_row)

    return related_rows


def test_pipeline_end_to_end_classifies_and_persists_all_outcomes(
    end_to_end_csv: Path,
):
    result = process_csv(end_to_end_csv)

    assert len(result["accepted"]) == 2
    assert len(result["quarantined"]) == 3
    assert result["skipped_duplicate_rows"] == [3, 7]

    assert (
        len(result["accepted"])
        + len(result["quarantined"])
        + len(result["skipped_duplicate_rows"])
    ) == 7

    accepted_panels = {
        reading["panel_id"]
        for reading in result["accepted"]
    }
    assert accepted_panels == {
        "PANEL_ACCEPTED_1",
        "PANEL_ACCEPTED_2",
    }

    quarantined_by_row = {
        reading["row"]: reading
        for reading in result["quarantined"]
    }
    assert set(quarantined_by_row) == {4, 5, 6}

    assert [
        error["type"]
        for error in quarantined_by_row[4]["errors"]
    ] == ["missing_value"]

    assert [
        error["type"]
        for error in quarantined_by_row[5]["errors"]
    ] == ["conflict"]

    assert [
        error["type"]
        for error in quarantined_by_row[6]["errors"]
    ] == ["conflict"]

    assert get_conflict_related_rows(
        quarantined_by_row[5]
    ) == {6}

    assert get_conflict_related_rows(
        quarantined_by_row[6]
    ) == {5}

    all_related_rows: set[int] = set()
    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 3 not in all_related_rows
    assert 7 not in all_related_rows

    inserted_readings = insert_readings(
        result["accepted"]
    )
    inserted_quarantined = insert_quarantined_readings(
        end_to_end_csv.name,
        result["quarantined"],
    )

    assert inserted_readings == 2
    assert inserted_quarantined == 3

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    panel_id,
                    irradiance_wm2
                FROM solar_readings
                WHERE site_id = %s
                ORDER BY panel_id;
                """,
                (TEST_SITE_ID,),
            )
            accepted_rows = cursor.fetchall()

    assert accepted_rows == [
        ("PANEL_ACCEPTED_1", 500.0),
        ("PANEL_ACCEPTED_2", 550.0),
    ]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    source_row,
                    raw_record,
                    errors
                FROM quarantined_readings
                WHERE source_file = %s
                ORDER BY source_row;
                """,
                (TEST_SOURCE_FILE,),
            )
            quarantined_rows = cursor.fetchall()

    assert len(quarantined_rows) == 3

    persisted_by_row = {
        source_row: {
            "record": raw_record,
            "errors": errors,
        }
        for source_row, raw_record, errors in quarantined_rows
    }

    assert set(persisted_by_row) == {4, 5, 6}

    assert (
        persisted_by_row[4]["record"]["temperature_c"]
        == ""
    )

    assert [
        error["type"]
        for error in persisted_by_row[4]["errors"]
    ] == ["missing_value"]

    assert [
        error["type"]
        for error in persisted_by_row[5]["errors"]
    ] == ["conflict"]
    assert persisted_by_row[5]["errors"][0].get(
        "related_row"
    ) == 6

    assert [
        error["type"]
        for error in persisted_by_row[6]["errors"]
    ] == ["conflict"]
    assert persisted_by_row[6]["errors"][0].get(
        "related_row"
    ) == 5

    assert 3 not in persisted_by_row
    assert 7 not in persisted_by_row


def test_pipeline_end_to_end_is_idempotent(
    end_to_end_csv: Path,
):
    first_result = process_csv(end_to_end_csv)

    first_inserted_readings = insert_readings(
        first_result["accepted"]
    )
    first_inserted_quarantined = insert_quarantined_readings(
        end_to_end_csv.name,
        first_result["quarantined"],
    )

    assert first_inserted_readings == 2
    assert first_inserted_quarantined == 3

    second_result = process_csv(end_to_end_csv)

    second_inserted_readings = insert_readings(
        second_result["accepted"]
    )
    second_inserted_quarantined = insert_quarantined_readings(
        end_to_end_csv.name,
        second_result["quarantined"],
    )

    assert second_result == first_result
    assert second_inserted_readings == 0
    assert second_inserted_quarantined == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE site_id = %s;
                """,
                (TEST_SITE_ID,),
            )
            accepted_count = cursor.fetchone()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )
            quarantined_count = cursor.fetchone()

    assert accepted_count is not None
    assert quarantined_count is not None
    assert accepted_count[0] == 2
    assert quarantined_count[0] == 3


def test_pipeline_rolls_back_both_tables_when_quarantine_fails(
    end_to_end_csv: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from psycopg.errors import CheckViolation

    original_result = process_csv(end_to_end_csv)

    invalid_quarantine: QuarantinedReading = {
        "row": 1,  # Violates CHECK (source_row >= 2)
        "record": dict(
            original_result["quarantined"][0]["record"]
        ),
        "errors": list(
            original_result["quarantined"][0]["errors"]
        ),
    }

    invalid_result: IngestionResult = {
        "accepted": original_result["accepted"],
        "quarantined": [
            *original_result["quarantined"],
            invalid_quarantine,
        ],
        "skipped_duplicate_rows": (
            original_result["skipped_duplicate_rows"]
        ),
    }

    # Simulate a classification result containing an
    # invalid source row to trigger a database failure.
    monkeypatch.setattr(
        "src.database.process_csv",
        lambda _: invalid_result,
    )

    with pytest.raises(CheckViolation):
        ingest_csv(end_to_end_csv)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE site_id = %s;
                """,
                (TEST_SITE_ID,),
            )
            accepted_count = cursor.fetchone()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )
            quarantined_count = cursor.fetchone()

    assert accepted_count is not None
    assert quarantined_count is not None

    assert accepted_count[0] == 0
    assert quarantined_count[0] == 0


def test_pipeline_records_successful_runs_and_reprocessing(
    end_to_end_csv: Path,
):
    # First execution: all distinct records are new.
    first_result, first_inserted, first_quarantined = (
        ingest_csv(end_to_end_csv)
    )

    assert len(first_result["accepted"]) == 2
    assert len(first_result["quarantined"]) == 3
    assert first_result["skipped_duplicate_rows"] == [3, 7]

    assert first_inserted == 2
    assert first_quarantined == 3

    # Second execution: all records already exist.
    second_result, second_inserted, second_quarantined = (
        ingest_csv(end_to_end_csv)
    )

    assert second_result == first_result
    assert second_inserted == 0
    assert second_quarantined == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    accepted_count,
                    inserted_readings_count,
                    quarantined_count,
                    inserted_quarantined_count,
                    duplicate_count,
                    finished_at IS NOT NULL
                FROM ingestion_runs
                WHERE source_file = %s
                ORDER BY id;
                """,
                (TEST_SOURCE_FILE,),
            )

            runs = cursor.fetchall()

    assert runs == [
        ("success", 2, 2, 3, 3, 2, True),
        ("success", 2, 0, 3, 0, 2, True),
    ]


def test_pipeline_records_failed_run_when_csv_is_missing(
    tmp_path: Path,
):
    missing_csv = tmp_path / TEST_SOURCE_FILE

    assert not missing_csv.exists()

    with pytest.raises(FileNotFoundError):
        ingest_csv(missing_csv)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    finished_at,
                    error_message
                FROM ingestion_runs
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )

            run = cursor.fetchone()

    assert run is not None
    assert run[0] == "failed"
    assert run[1] is not None
    assert run[2] is not None
    assert TEST_SOURCE_FILE in run[2]