import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Any
import pytest
import psycopg

from psycopg.errors import CheckViolation

from src.database import (
    get_connection,
    insert_quarantined_readings,
    insert_readings,
    start_ingestion_run
)
from src.validate_readings import (
    AcceptedReading,
    QuarantinedReading,
    process_csv,
    IngestionResult
)


TEST_SITE_ID = "PYTEST_SITE"
TEST_SITE_ID_2 = "PYTEST_SITE_2"
TEST_PANEL_ID = "PYTEST_PANEL"

TEST_TIMESTAMP = datetime(
    2099,
    1,
    1,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

TEST_SOURCE_FILE = "pytest_database.csv"
TEST_SOURCE_FILE_2 = "pytest_database_2.csv"

CSV_FIELDNAMES = [
    "timestamp",
    "site_id",
    "panel_id",
    "irradiance_wm2",
    "temperature_c",
    "voltage_v",
    "current_a",
]

MeasurementField = Literal[
    "irradiance_wm2",
    "voltage_v",
    "current_a",
]


# =========================================================
# Helpers
# =========================================================


def delete_test_data():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM solar_readings
                WHERE site_id IN (%s, %s);
                """,
                (
                    TEST_SITE_ID,
                    TEST_SITE_ID_2,
                ),
            )

            cursor.execute(
                """
                DELETE FROM quarantined_readings
                WHERE source_file IN (%s, %s);
                """,
                (
                    TEST_SOURCE_FILE,
                    TEST_SOURCE_FILE_2,
                ),
            )

            cursor.execute(
                """
                DELETE FROM ingestion_runs
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

    delete_test_data()

    yield

    delete_test_data()


def build_accepted_reading(
    irradiance: float = 500.0,
    *,
    timestamp: datetime = TEST_TIMESTAMP,
    site_id: str = TEST_SITE_ID,
    panel_id: str = TEST_PANEL_ID,
) -> AcceptedReading:
    return {
        "timestamp": timestamp,
        "site_id": site_id,
        "panel_id": panel_id,
        "irradiance_wm2": irradiance,
        "temperature_c": 25.0,
        "voltage_v": 35.0,
        "current_a": 5.0,
    }


def build_quarantined_reading(
    message: str = "Missing value",
    *,
    row: int = 2,
) -> QuarantinedReading:
    return {
        "row": row,
        "record": {
            "timestamp": "2099-01-01T12:00:00+00:00",
            "site_id": TEST_SITE_ID,
            "panel_id": TEST_PANEL_ID,
            "irradiance_wm2": "500.0",
            "temperature_c": "",
            "voltage_v": "35.0",
            "current_a": "5.0",
        },
        "errors": [
            {
                "type": "missing_value",
                "column": "temperature_c",
                "message": message,
                "invalid_value": "",
            }
        ],
    }


def build_negative_measurement_reading(
    field: MeasurementField,
) -> AcceptedReading:
    reading = build_accepted_reading(
        panel_id=f"PYTEST_NEGATIVE_{field}",
    )

    if field == "irradiance_wm2":
        reading["irradiance_wm2"] = -1.0
    elif field == "voltage_v":
        reading["voltage_v"] = -1.0
    else:
        reading["current_a"] = -1.0

    return reading


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


def write_readings_csv(
    tmp_path: Path,
    filename: str,
    rows: list[list[str]],
) -> Path:
    path = tmp_path / filename

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(CSV_FIELDNAMES)
        writer.writerows(rows)

    return path


# =========================================================
# Accepted readings
# =========================================================


def test_insert_readings_inserts_new_reading():
    reading = build_accepted_reading()

    inserted_count = insert_readings([reading])

    assert inserted_count == 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    site_id,
                    panel_id,
                    irradiance_wm2
                FROM solar_readings
                WHERE
                    timestamp = %s
                    AND site_id = %s
                    AND panel_id = %s;
                """,
                (
                    TEST_TIMESTAMP,
                    TEST_SITE_ID,
                    TEST_PANEL_ID,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == TEST_SITE_ID
    assert result[1] == TEST_PANEL_ID
    assert result[2] == 500.0


def test_insert_readings_is_idempotent():
    reading = build_accepted_reading()

    first_insert = insert_readings([reading])
    second_insert = insert_readings([reading])

    assert first_insert == 1
    assert second_insert == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE
                    timestamp = %s
                    AND site_id = %s
                    AND panel_id = %s;
                """,
                (
                    TEST_TIMESTAMP,
                    TEST_SITE_ID,
                    TEST_PANEL_ID,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 1


def test_insert_readings_duplicate_inside_same_batch_is_idempotent():
    reading = build_accepted_reading()

    inserted_count = insert_readings(
        [
            reading,
            reading,
        ]
    )

    assert inserted_count == 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE
                    timestamp = %s
                    AND site_id = %s
                    AND panel_id = %s;
                """,
                (
                    TEST_TIMESTAMP,
                    TEST_SITE_ID,
                    TEST_PANEL_ID,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 1


def test_insert_readings_unique_key_conflict_does_not_overwrite():
    original_reading = build_accepted_reading(
        irradiance=500.0
    )

    conflicting_reading = build_accepted_reading(
        irradiance=999.0
    )

    first_insert = insert_readings(
        [original_reading]
    )

    second_insert = insert_readings(
        [conflicting_reading]
    )

    assert first_insert == 1
    assert second_insert == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT irradiance_wm2
                FROM solar_readings
                WHERE
                    timestamp = %s
                    AND site_id = %s
                    AND panel_id = %s;
                """,
                (
                    TEST_TIMESTAMP,
                    TEST_SITE_ID,
                    TEST_PANEL_ID,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 500.0


def test_insert_readings_composite_key_distinguishes_site_and_panel():
    base_reading = build_accepted_reading()

    different_panel = build_accepted_reading(
        panel_id="PYTEST_PANEL_2",
    )

    different_site = build_accepted_reading(
        site_id=TEST_SITE_ID_2,
    )

    inserted_count = insert_readings(
        [
            base_reading,
            different_panel,
            different_site,
        ]
    )

    assert inserted_count == 3

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE
                    timestamp = %s
                    AND site_id IN (%s, %s);
                """,
                (
                    TEST_TIMESTAMP,
                    TEST_SITE_ID,
                    TEST_SITE_ID_2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 3


@pytest.mark.parametrize(
    "field",
    [
        "irradiance_wm2",
        "voltage_v",
        "current_a",
    ],
)
def test_database_rejects_negative_nonnegative_measurements(
    field: MeasurementField,
):
    reading = build_negative_measurement_reading(field)

    with pytest.raises(CheckViolation):
        insert_readings([reading])

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE
                    site_id = %s
                    AND panel_id = %s;
                """,
                (
                    reading["site_id"],
                    reading["panel_id"],
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 0


def test_insert_readings_rolls_back_entire_transaction_on_failure():
    valid_reading = build_accepted_reading(
        timestamp=datetime(
            2099,
            1,
            2,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        panel_id="PYTEST_VALID",
    )

    invalid_reading: AcceptedReading = {
        "timestamp": datetime(
            2099,
            1,
            2,
            12,
            5,
            0,
            tzinfo=timezone.utc,
        ),
        "site_id": TEST_SITE_ID,
        "panel_id": "PYTEST_INVALID",
        "irradiance_wm2": 500.0,
        "temperature_c": 25.0,
        "voltage_v": -10.0,
        "current_a": 5.0,
    }

    with pytest.raises(CheckViolation):
        insert_readings(
            [
                valid_reading,
                invalid_reading,
            ]
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE site_id = %s
                AND panel_id IN (
                    'PYTEST_VALID',
                    'PYTEST_INVALID'
                );
                """,
                (TEST_SITE_ID,),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 0


def test_insert_readings_empty_list_does_nothing():
    inserted_count = insert_readings([])

    assert inserted_count == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM solar_readings
                WHERE site_id IN (%s, %s);
                """,
                (
                    TEST_SITE_ID,
                    TEST_SITE_ID_2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 0


def test_insert_readings_mixed_existing_and_new():
    existing_reading = build_accepted_reading()

    new_reading_1 = build_accepted_reading(
        timestamp=datetime(
            2099,
            1,
            1,
            12,
            5,
            0,
            tzinfo=timezone.utc,
        ),
        panel_id="PYTEST_PANEL_2",
        irradiance=510.0,
    )

    new_reading_2 = build_accepted_reading(
        timestamp=datetime(
            2099,
            1,
            1,
            12,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        panel_id="PYTEST_PANEL_3",
        irradiance=520.0,
    )
    new_reading_2["temperature_c"] = 26.0
    new_reading_2["voltage_v"] = 36.0
    new_reading_2["current_a"] = 5.2

    first_insert = insert_readings(
        [existing_reading]
    )

    mixed_insert = insert_readings(
        [
            existing_reading,
            new_reading_1,
            new_reading_2,
        ]
    )

    assert first_insert == 1
    assert mixed_insert == 2

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

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 3


# =========================================================
# Quarantined readings
# =========================================================


def test_insert_quarantined_readings_inserts_new_record():
    reading = build_quarantined_reading()

    inserted_count = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [reading],
    )

    assert inserted_count == 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    source_file,
                    source_row,
                    raw_record,
                    errors
                FROM quarantined_readings
                WHERE
                    source_file = %s
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None

    assert result[0] == TEST_SOURCE_FILE
    assert result[1] == 2

    raw_record = result[2]
    errors = result[3]

    assert raw_record["temperature_c"] == ""
    assert errors[0]["type"] == "missing_value"
    assert errors[0]["column"] == "temperature_c"


def test_insert_quarantined_readings_is_idempotent():
    reading = build_quarantined_reading()

    first_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [reading],
    )

    second_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [reading],
    )

    assert first_insert == 1
    assert second_insert == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE
                    source_file = %s
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 1


def test_insert_quarantined_readings_duplicate_inside_same_batch_is_idempotent():
    reading = build_quarantined_reading()

    inserted_count = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [
            reading,
            reading,
        ],
    )

    assert inserted_count == 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE
                    source_file = %s
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 1


def test_quarantine_unique_key_conflict_does_not_overwrite():
    original_reading = build_quarantined_reading(
        message="Missing value"
    )

    conflicting_reading = build_quarantined_reading(
        message="Different error message"
    )

    first_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [original_reading],
    )

    second_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [conflicting_reading],
    )

    assert first_insert == 1
    assert second_insert == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT errors
                FROM quarantined_readings
                WHERE
                    source_file = %s
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None

    errors = result[0]

    assert errors[0]["message"] == "Missing value"


def test_quarantine_unique_key_is_scoped_by_source_file():
    reading = build_quarantined_reading()

    first_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [reading],
    )

    second_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE_2,
        [reading],
    )

    assert first_insert == 1
    assert second_insert == 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE
                    source_file IN (%s, %s)
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    TEST_SOURCE_FILE_2,
                    2,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 2


def test_insert_quarantined_readings_rolls_back_entire_transaction_on_failure():
    valid_reading = build_quarantined_reading(
        row=2,
    )

    invalid_reading = build_quarantined_reading(
        row=1,
    )

    with pytest.raises(CheckViolation):
        insert_quarantined_readings(
            TEST_SOURCE_FILE,
            [
                valid_reading,
                invalid_reading,
            ],
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 0


def test_insert_quarantined_readings_empty_list_does_nothing():
    inserted_count = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [],
    )

    assert inserted_count == 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 0


def test_insert_quarantined_readings_mixed_existing_and_new():
    existing_reading = build_quarantined_reading(
        row=2,
    )

    new_reading_1 = build_quarantined_reading(
        row=3,
    )

    new_reading_2 = build_quarantined_reading(
        row=4,
    )

    first_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [existing_reading],
    )

    mixed_insert = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [
            existing_reading,
            new_reading_1,
            new_reading_2,
        ],
    )

    assert first_insert == 1
    assert mixed_insert == 2

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE source_file = %s;
                """,
                (TEST_SOURCE_FILE,),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 3


def test_insert_quarantined_reading_preserves_multiple_errors():
    reading: QuarantinedReading = {
        "row": 10,
        "record": {
            "timestamp": "not-a-timestamp",
            "site_id": TEST_SITE_ID,
            "panel_id": TEST_PANEL_ID,
            "irradiance_wm2": "-45.0",
            "temperature_c": "",
            "voltage_v": "35.0",
            "current_a": "5.0",
        },
        "errors": [
            {
                "type": "timestamp_error",
                "column": "timestamp",
                "message": "Invalid timestamp format",
                "invalid_value": "not-a-timestamp",
            },
            {
                "type": "domain_violation",
                "column": "irradiance_wm2",
                "message": (
                    "Irradiance cannot be a negative value"
                ),
                "invalid_value": "-45.0",
            },
            {
                "type": "missing_value",
                "column": "temperature_c",
                "message": "Missing value",
                "invalid_value": "",
            },
        ],
    }

    inserted_count = insert_quarantined_readings(
        TEST_SOURCE_FILE,
        [reading],
    )

    assert inserted_count == 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    raw_record,
                    errors
                FROM quarantined_readings
                WHERE
                    source_file = %s
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    10,
                ),
            )

            result = cursor.fetchone()

    assert result is not None

    raw_record = result[0]
    errors = result[1]

    assert raw_record == reading["record"]
    assert errors == reading["errors"]

    assert [
        error["type"]
        for error in errors
    ] == [
        "timestamp_error",
        "domain_violation",
        "missing_value",
    ]


def test_insert_quarantined_readings_rejects_empty_errors():
    reading = build_quarantined_reading(
        row=11,
    )
    reading["errors"] = []

    with pytest.raises(CheckViolation):
        insert_quarantined_readings(
            TEST_SOURCE_FILE,
            [reading],
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quarantined_readings
                WHERE
                    source_file = %s
                    AND source_row = %s;
                """,
                (
                    TEST_SOURCE_FILE,
                    11,
                ),
            )

            result = cursor.fetchone()

    assert result is not None
    assert result[0] == 0


# =========================================================
# process_csv
# =========================================================


def test_process_csv_conflict_after_invalid_reading():
    path = (
        Path(__file__).parent
        / "fixtures/process_invalid_then_conflict.csv"
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == []

    assert len(result["quarantined"]) == 2

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {2, 3}

    row_2 = quarantined_by_row[2]
    row_3 = quarantined_by_row[3]

    assert any(
        error["type"] == "missing_value"
        and error.get("column") == "temperature_c"
        for error in row_2["errors"]
    )

    assert any(
        error["type"] == "conflict"
        and error.get("related_row") == 3
        for error in row_2["errors"]
    )

    assert any(
        error["type"] == "conflict"
        and error.get("related_row") == 2
        for error in row_3["errors"]
    )


def test_process_csv_duplicate_invalid_reading_is_skipped():
    path = (
        Path(__file__).parent
        / "fixtures/process_duplicate_invalid_readings.csv"
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == [3]
    assert len(result["quarantined"]) == 1

    quarantined = result["quarantined"][0]

    assert quarantined["row"] == 2
    assert len(quarantined["errors"]) == 1

    error = quarantined["errors"][0]

    assert error["type"] == "missing_value"
    assert error.get("column") == "temperature_c"
    assert error["message"] == "Missing value"


def test_process_csv_groups_conflicts_and_skips_exact_duplicate():
    path = (
        Path(__file__).parent
        / "fixtures/process_grouped_conflicts.csv"
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == [5]
    assert len(result["quarantined"]) == 3

    quarantined_rows = {
        item["row"]
        for item in result["quarantined"]
    }

    assert quarantined_rows == {2, 3, 4}


def test_process_csv_grouped_conflicts_reference_all_distinct_rows():
    path = (
        Path(__file__).parent
        / "fixtures/process_grouped_conflicts.csv"
    )

    result = process_csv(path)

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {2, 3, 4}

    expected_related_rows = {
        2: {3, 4},
        3: {2, 4},
        4: {2, 3},
    }

    for row_number, expected_rows in expected_related_rows.items():
        reading = quarantined_by_row[row_number]

        conflict_errors = [
            error
            for error in reading["errors"]
            if error["type"] == "conflict"
        ]

        related_rows = get_conflict_related_rows(
            reading
        )

        assert related_rows == expected_rows
        assert len(conflict_errors) == 2

    all_related_rows: set[int] = set()

    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 5 not in all_related_rows


def test_process_csv_grouped_conflicts_are_independent_of_record_order():
    path = (
        Path(__file__).parent
        / "fixtures/process_grouped_conflicts_shuffled.csv"
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == [5]
    assert len(result["quarantined"]) == 3

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {2, 3, 4}

    irradiance_values = {
        item["record"]["irradiance_wm2"]
        for item in result["quarantined"]
    }

    assert irradiance_values == {
        "215.4",
        "250.0",
        "300.0",
    }

    expected_related_rows = {
        2: {3, 4},
        3: {2, 4},
        4: {2, 3},
    }

    for row_number, expected_rows in expected_related_rows.items():
        reading = quarantined_by_row[row_number]

        conflict_errors = [
            error
            for error in reading["errors"]
            if error["type"] == "conflict"
        ]

        related_rows = get_conflict_related_rows(
            reading
        )

        assert related_rows == expected_rows
        assert len(conflict_errors) == 2

    all_related_rows: set[int] = set()

    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 5 not in all_related_rows


def test_process_csv_keeps_conflict_groups_isolated_by_natural_key():
    path = (
        Path(__file__).parent
        / "fixtures/process_multiple_natural_key_groups.csv"
    )

    result = process_csv(path)

    assert len(result["accepted"]) == 1
    assert len(result["quarantined"]) == 4
    assert result["skipped_duplicate_rows"] == []

    accepted = result["accepted"][0]

    assert accepted["site_id"] == "GO_ANAPOLIS_01"
    assert accepted["panel_id"] == "GTX_14553"
    assert accepted["irradiance_wm2"] == 350.0

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {
        2,
        3,
        4,
        5,
    }

    expected_related_rows = {
        2: {3},
        3: {2},
        4: {5},
        5: {4},
    }

    for row_number, expected_rows in expected_related_rows.items():
        reading = quarantined_by_row[row_number]

        conflict_errors = [
            error
            for error in reading["errors"]
            if error["type"] == "conflict"
        ]

        related_rows = get_conflict_related_rows(
            reading
        )

        assert related_rows == expected_rows
        assert len(conflict_errors) == 1


def test_process_csv_group_with_invalid_conflicts_and_duplicate():
    path = (
        Path(__file__).parent
        / "fixtures/process_invalid_multiple_conflicts_duplicate.csv"
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == [5]
    assert len(result["quarantined"]) == 3

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {
        2,
        3,
        4,
    }

    row_2 = quarantined_by_row[2]
    row_3 = quarantined_by_row[3]
    row_4 = quarantined_by_row[4]

    row_2_error_types = [
        error["type"]
        for error in row_2["errors"]
    ]

    assert row_2_error_types == [
        "missing_value",
        "conflict",
        "conflict",
    ]

    row_3_error_types = [
        error["type"]
        for error in row_3["errors"]
    ]

    assert row_3_error_types == [
        "conflict",
        "conflict",
    ]

    row_4_error_types = [
        error["type"]
        for error in row_4["errors"]
    ]

    assert row_4_error_types == [
        "conflict",
        "conflict",
    ]

    expected_related_rows = {
        2: {3, 4},
        3: {2, 4},
        4: {2, 3},
    }

    for row_number, expected_rows in expected_related_rows.items():
        reading = quarantined_by_row[row_number]

        related_rows = get_conflict_related_rows(
            reading
        )

        assert related_rows == expected_rows

    all_related_rows: set[int] = set()

    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 5 not in all_related_rows


def test_process_csv_skips_multiple_exact_duplicates_of_conflicting_version(
    tmp_path: Path,
):
    path = write_readings_csv(
        tmp_path,
        "multiple_duplicates_conflict.csv",
        [
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "215.4",
                "22.8",
                "31.2",
                "2.8",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "250.0",
                "23.1",
                "32.0",
                "3.1",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "250.0",
                "23.1",
                "32.0",
                "3.1",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "250.0",
                "23.1",
                "32.0",
                "3.1",
            ],
        ],
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == [4, 5]

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {2, 3}

    assert get_conflict_related_rows(
        quarantined_by_row[2]
    ) == {3}

    assert get_conflict_related_rows(
        quarantined_by_row[3]
    ) == {2}

    all_related_rows: set[int] = set()

    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 4 not in all_related_rows
    assert 5 not in all_related_rows


def test_process_csv_skips_duplicate_of_first_version_before_conflict_analysis(
    tmp_path: Path,
):
    path = write_readings_csv(
        tmp_path,
        "duplicate_first_version.csv",
        [
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "215.4",
                "22.8",
                "31.2",
                "2.8",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "215.4",
                "22.8",
                "31.2",
                "2.8",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "250.0",
                "23.1",
                "32.0",
                "3.1",
            ],
        ],
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert result["skipped_duplicate_rows"] == [3]

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {2, 4}

    assert get_conflict_related_rows(
        quarantined_by_row[2]
    ) == {4}

    assert get_conflict_related_rows(
        quarantined_by_row[4]
    ) == {2}

    all_related_rows: set[int] = set()

    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 3 not in all_related_rows


def test_process_csv_keeps_duplicates_isolated_between_natural_key_groups(
    tmp_path: Path,
):
    path = write_readings_csv(
        tmp_path,
        "isolated_duplicate_groups.csv",
        [
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "215.4",
                "22.8",
                "31.2",
                "2.8",
            ],
            [
                "2026-09-17T08:05:00+00:00",
                "GO_GOIANIA_01",
                "GTX_14552",
                "300.0",
                "24.0",
                "33.0",
                "3.5",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "250.0",
                "23.1",
                "32.0",
                "3.1",
            ],
            [
                "2026-09-17T08:00:00+00:00",
                "GO_ANAPOLIS_01",
                "GTX_14551",
                "250.0",
                "23.1",
                "32.0",
                "3.1",
            ],
            [
                "2026-09-17T08:05:00+00:00",
                "GO_GOIANIA_01",
                "GTX_14552",
                "300.0",
                "24.0",
                "33.0",
                "3.5",
            ],
        ],
    )

    result = process_csv(path)

    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["site_id"] == "GO_GOIANIA_01"
    assert result["accepted"][0]["panel_id"] == "GTX_14552"

    assert result["skipped_duplicate_rows"] == [5, 6]

    quarantined_by_row = {
        item["row"]: item
        for item in result["quarantined"]
    }

    assert set(quarantined_by_row) == {2, 4}

    assert get_conflict_related_rows(
        quarantined_by_row[2]
    ) == {4}

    assert get_conflict_related_rows(
        quarantined_by_row[4]
    ) == {2}

    all_related_rows: set[int] = set()

    for reading in result["quarantined"]:
        all_related_rows.update(
            get_conflict_related_rows(reading)
        )

    assert 3 not in all_related_rows
    assert 5 not in all_related_rows
    assert 6 not in all_related_rows


def test_start_ingestion_run_creates_running_record():
    run_id = start_ingestion_run(TEST_SOURCE_FILE)

    assert run_id > 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    source_file,
                    status,
                    started_at,
                    finished_at,
                    accepted_count,
                    inserted_readings_count,
                    quarantined_count,
                    inserted_quarantined_count,
                    duplicate_count,
                    error_message
                FROM ingestion_runs
                WHERE id = %s;
                """,
                (run_id,),
            )

            result = cursor.fetchone()

    assert result is not None

    assert result[0] == TEST_SOURCE_FILE
    assert result[1] == "running"
    assert result[2] is not None
    assert result[2].tzinfo is not None
    assert result[3] is None
    assert result[4:9] == (0, 0, 0, 0, 0)
    assert result[9] is None


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
                f"Ingestion run {run_id} is not running "
                "or does not exist"
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
                    f"Ingestion run {run_id} is not running "
                    "or does not exist"
                )

def test_finish_ingestion_run_success_records_counts():
    run_id = start_ingestion_run(TEST_SOURCE_FILE)

    result: IngestionResult = {
        "accepted": [build_accepted_reading()],
        "quarantined": [build_quarantined_reading()],
        "skipped_duplicate_rows": [3],
    }

    with get_connection() as connection:
        inserted_readings = insert_readings(
            result["accepted"],
            connection=connection,
        )

        inserted_quarantined = insert_quarantined_readings(
            TEST_SOURCE_FILE,
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

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    finished_at,
                    accepted_count,
                    inserted_readings_count,
                    quarantined_count,
                    inserted_quarantined_count,
                    duplicate_count,
                    error_message
                FROM ingestion_runs
                WHERE id = %s;
                """,
                (run_id,),
            )

            run = cursor.fetchone()

    assert run is not None

    assert run[0] == "success"
    assert run[1] is not None
    assert run[2:7] == (1, 1, 1, 1, 1)
    assert run[7] is None


def test_finish_ingestion_run_failed_records_error():
    run_id = start_ingestion_run(TEST_SOURCE_FILE)

    finish_ingestion_run_failed(
        run_id,
        "Simulated database failure",
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    finished_at,
                    error_message
                FROM ingestion_runs
                WHERE id = %s;
                """,
                (run_id,),
            )

            run = cursor.fetchone()

    assert run is not None

    assert run[0] == "failed"
    assert run[1] is not None
    assert run[2] == "Simulated database failure"