from pathlib import Path
from datetime import datetime
import pytest

from src.validate_readings import (
    ValidationErrors,
    build_natural_key,
    check_reading_uniqueness,
    count_errors,
    parse_numeric_value,
    process_csv,
    validate_csv,
    validate_domain_rule,
    validate_row_fields,
    validate_timestamp,
)


# =========================================================
# Unit Tests
# =========================================================


def test_parse_float_value():
    assert parse_numeric_value("215.4") == 215.4


def test_negative_value():
    assert parse_numeric_value("-45.0") == -45.0


def test_zero_value():
    assert parse_numeric_value("0") == 0.0


def test_empty_value():
    assert parse_numeric_value("") is None


def test_whitespace_value():
    assert parse_numeric_value("   ") is None


def test_whitespace_around_value():
    assert parse_numeric_value(" 30.5 ") == 30.5


def test_alphabet_value():
    with pytest.raises(ValueError):
        parse_numeric_value("abc")


def test_normal_behaviour_build_natural_key():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "215.4",
    }

    expected_key = (
        "2026-09-17T08:00:00+00:00",
        "GO_ANAPOLIS_01",
        "GTX_14551",
    )

    assert build_natural_key(row) == expected_key


def test_build_natural_key_identity_reading_with_different_temperature_irradiance():
    row1 = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "315.4",
        "temperature_c": "25.0",
    }

    row2 = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "215.4",
        "temperature_c": "35.0",
    }

    assert build_natural_key(row1) == build_natural_key(row2)


def test_validate_domain_rule_normal_behaviour():
    assert validate_domain_rule(
        "irradiance_wm2",
        500.0,
    ) == (True, None)


def test_validate_domain_rule_zero_value():
    assert validate_domain_rule(
        "irradiance_wm2",
        0.0,
    ) == (True, None)


def test_validate_domain_rule_negative_value():
    assert validate_domain_rule(
        "irradiance_wm2",
        -45.0,
    ) == (
        False,
        "Irradiance cannot be a negative value",
    )


def test_validate_domain_value_temperature():
    assert validate_domain_rule(
        "temperature_c",
        -5.0,
    ) == (True, None)


def test_check_reading_uniqueness_new_reading():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "315.4",
        "temperature_c": "25.0",
        "voltage_v": "35.9",
        "current_a": "5.1",
    }

    seen_readings = {}

    assert check_reading_uniqueness(
        row,
        seen_readings,
    ) == ("new", None)

    assert seen_readings == {}


def test_check_reading_uniqueness_duplicate_reading():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "315.4",
        "temperature_c": "25.0",
        "voltage_v": "35.9",
        "current_a": "5.1",
    }

    key = build_natural_key(row)

    seen_readings = {
        key: [2, row],
    }

    assert check_reading_uniqueness(
        row,
        seen_readings,
    ) == ("duplicate", 2)


def test_check_reading_uniqueness_conflict_reading():
    row1 = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "315.4",
        "temperature_c": "25.0",
        "voltage_v": "35.9",
        "current_a": "5.1",
    }

    row2 = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "215.4",
        "temperature_c": "35.0",
        "voltage_v": "35.9",
        "current_a": "5.1",
    }

    key = build_natural_key(row1)

    seen_readings = {
        key: [2, row1],
    }

    assert check_reading_uniqueness(
        row2,
        seen_readings,
    ) == ("conflict", 2)


def test_count_errors_zero():
    errors: ValidationErrors = {
        "missing_value": [],
        "conversion_error": [],
        "domain_violation": [],
        "timestamp_error": [],
        "duplicate": [],
        "conflict": [],
    }

    assert count_errors(errors) == 0


def test_count_multiple_errors():
    errors: ValidationErrors = {
        "missing_value": [
            {
                "row": 2,
                "column": "temperature_c",
                "message": "Missing value",
            },
            {
                "row": 3,
                "column": "temperature_c",
                "message": "Missing value",
            },
        ],
        "conversion_error": [
            {
                "row": 4,
                "column": "temperature_c",
                "message": "Conversion error",
                "invalid_value": "abc",
            },
        ],
        "domain_violation": [],
        "timestamp_error": [],
        "duplicate": [],
        "conflict": [
            {
                "row": 6,
                "related_row": 5,
                "message": "Conflicting reading",
            },
        ],
    }

    assert count_errors(errors) == 4


def test_validate_timestamp_valid_with_timezone():
    timestamp = "2026-09-17T08:00:00+00:00"

    assert validate_timestamp(timestamp) is None


def test_validate_timestamp_without_timezone():
    timestamp = "2026-09-17T08:00:00"

    assert (
        validate_timestamp(timestamp)
        == "Timestamp must include timezone information"
    )


def test_validate_timestamp_malformed():
    timestamp = "not-a-timestamp"

    assert (
        validate_timestamp(timestamp)
        == "Invalid timestamp format"
    )


def test_validate_row_fields_valid_row():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "215.4",
        "temperature_c": "22.8",
        "voltage_v": "31.2",
        "current_a": "2.8",
    }

    errors = validate_row_fields(row)

    assert errors == []


def test_validate_row_fields_missing_value():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "215.4",
        "temperature_c": "",
        "voltage_v": "31.2",
        "current_a": "2.8",
    }

    errors = validate_row_fields(row)

    assert len(errors) == 1

    error = errors[0]

    assert error["type"] == "missing_value"
    assert error.get("column") == "temperature_c"
    assert error["message"] == "Missing value"
    assert error.get("invalid_value") == ""


def test_validate_row_fields_domain_violation():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "-45.0",
        "temperature_c": "22.8",
        "voltage_v": "31.2",
        "current_a": "2.8",
    }

    errors = validate_row_fields(row)

    assert len(errors) == 1

    error = errors[0]

    assert error["type"] == "domain_violation"
    assert error.get("column") == "irradiance_wm2"
    assert (
        error["message"]
        == "Irradiance cannot be a negative value"
    )
    assert error.get("invalid_value") == "-45.0"


def test_validate_row_fields_conversion_error():
    row = {
        "timestamp": "2026-09-17T08:00:00+00:00",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "215.4",
        "temperature_c": "abc",
        "voltage_v": "31.2",
        "current_a": "2.8",
    }

    errors = validate_row_fields(row)

    assert len(errors) == 1

    error = errors[0]

    assert error["type"] == "conversion_error"
    assert error.get("column") == "temperature_c"
    assert error["message"] == "Conversion error"
    assert error.get("invalid_value") == "abc"


def test_validate_row_fields_multiple_errors():
    row = {
        "timestamp": "not-a-timestamp",
        "site_id": "GO_ANAPOLIS_01",
        "panel_id": "GTX_14551",
        "irradiance_wm2": "-45.0",
        "temperature_c": "",
        "voltage_v": "abc",
        "current_a": "2.8",
    }

    errors = validate_row_fields(row)

    assert len(errors) == 4

    assert any(
        error["type"] == "timestamp_error"
        for error in errors
    )

    assert any(
        error["type"] == "domain_violation"
        and error.get("column") == "irradiance_wm2"
        for error in errors
    )

    assert any(
        error["type"] == "missing_value"
        and error.get("column") == "temperature_c"
        for error in errors
    )

    assert any(
        error["type"] == "conversion_error"
        and error.get("column") == "voltage_v"
        for error in errors
    )


# =========================================================
# Integration Tests
# =========================================================


def test_validate_csv_normal_behaviour():
    path = (
        Path(__file__).parent
        / "fixtures/valid_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 0


def test_validate_csv_missing_value():
    path = (
        Path(__file__).parent
        / "fixtures/missing_values_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1

    error = errors["missing_value"][0]

    assert error["row"] == 3
    assert error["column"] == "temperature_c"
    assert error["message"] == "Missing value"


def test_validate_csv_negative_values():
    path = (
        Path(__file__).parent
        / "fixtures/negative_values_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1

    error = errors["domain_violation"][0]

    assert error["row"] == 3
    assert error["column"] == "irradiance_wm2"
    assert (
        error["message"]
        == "Irradiance cannot be a negative value"
    )
    assert error["invalid_value"] == "-45.0"


def test_validate_csv_invalid_number_values():
    path = (
        Path(__file__).parent
        / "fixtures/invalid_number_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1

    error = errors["conversion_error"][0]

    assert error["row"] == 3
    assert error["column"] == "temperature_c"
    assert error["message"] == "Conversion error"
    assert error["invalid_value"] == "abc"


def test_validate_csv_duplicated_values():
    path = (
        Path(__file__).parent
        / "fixtures/duplicate_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1

    error = errors["duplicate"][0]

    assert error["row"] == 4
    assert error["related_row"] == 3
    assert error["message"] == "Duplicate reading"


def test_validate_csv_conflict_values():
    path = (
        Path(__file__).parent
        / "fixtures/conflict_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1

    error = errors["conflict"][0]

    assert error["row"] == 4
    assert error["related_row"] == 3
    assert error["message"] == "Conflicting reading"


def test_validate_csv_multiple_errors():
    path = (
        Path(__file__).parent
        / "fixtures/multiple_errors_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 4

    assert len(errors["missing_value"]) == 1
    assert len(errors["conversion_error"]) == 0
    assert len(errors["domain_violation"]) == 1
    assert len(errors["timestamp_error"]) == 0
    assert len(errors["duplicate"]) == 1
    assert len(errors["conflict"]) == 1

    assert (
        errors["missing_value"][0]["column"]
        == "temperature_c"
    )

    assert (
        errors["domain_violation"][0]["column"]
        == "irradiance_wm2"
    )

    assert (
        errors["duplicate"][0]["related_row"]
        == 5
    )

    assert (
        errors["conflict"][0]["related_row"]
        == 7
    )


def test_validate_csv_missing_column():
    path = (
        Path(__file__).parent
        / "fixtures/missing_column_readings.csv"
    )

    with pytest.raises(ValueError) as error:
        validate_csv(path)

    assert "Missing columns" in str(error.value)
    assert "irradiance_wm2" in str(error.value)


def test_validate_csv_multiple_missing_columns():
    path = (
        Path(__file__).parent
        / "fixtures/missing_columns_readings.csv"
    )

    with pytest.raises(ValueError) as error:
        validate_csv(path)

    assert "Missing columns" in str(error.value)
    assert "irradiance_wm2" in str(error.value)
    assert "voltage_v" in str(error.value)


def test_extra_columns_readings():
    path = (
        Path(__file__).parent
        / "fixtures/extra_columns_readings.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 0


def test_validate_csv_valid_timestamp():
    path = (
        Path(__file__).parent
        / "fixtures/valid_readings.csv"
    )

    errors = validate_csv(path)

    assert errors["timestamp_error"] == []


def test_validate_csv_timestamp_without_timezone():
    path = (
        Path(__file__).parent
        / "fixtures/timestamp_without_timezone.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1
    assert len(errors["timestamp_error"]) == 1

    error = errors["timestamp_error"][0]

    assert error["row"] == 2
    assert error["column"] == "timestamp"

    assert (
        error["message"]
        == "Timestamp must include timezone information"
    )

    assert (
        error["invalid_value"]
        == "2026-09-17T08:00:00"
    )


def test_validate_csv_malformed_timestamp():
    path = (
        Path(__file__).parent
        / "fixtures/malformed_timestamp.csv"
    )

    errors = validate_csv(path)

    assert count_errors(errors) == 1
    assert len(errors["timestamp_error"]) == 1

    error = errors["timestamp_error"][0]

    assert error["row"] == 2
    assert error["column"] == "timestamp"
    assert error["message"] == "Invalid timestamp format"
    assert error["invalid_value"] == "not-a-timestamp"

def test_process_csv_valid_reading():
    path = (
        Path(__file__).parent
        / "fixtures/process_valid_readings.csv"
    )

    result = process_csv(path)

    assert len(result["accepted"]) == 1
    assert result["quarantined"] == []
    assert result["skipped_duplicate_rows"] == []

    reading = result["accepted"][0]

    assert reading["site_id"] == "GO_ANAPOLIS_01"
    assert reading["panel_id"] == "GTX_14551"

    assert isinstance(reading["timestamp"], datetime)
    assert reading["timestamp"].tzinfo is not None
    assert reading["timestamp"].utcoffset() is not None

    assert reading["irradiance_wm2"] == 215.4
    assert reading["temperature_c"] == 22.8
    assert reading["voltage_v"] == 31.2
    assert reading["current_a"] == 2.8

    assert isinstance(reading["irradiance_wm2"], float)
    assert isinstance(reading["temperature_c"], float)
    assert isinstance(reading["voltage_v"], float)
    assert isinstance(reading["current_a"], float)

def test_process_csv_invalid_reading_goes_to_quarantine():
    path = (
        Path(__file__).parent
        / "fixtures/process_invalid_reading.csv"
    )

    result = process_csv(path)

    assert result["accepted"] == []
    assert len(result["quarantined"]) == 1
    assert result["skipped_duplicate_rows"] == []

    quarantined = result["quarantined"][0]

    assert quarantined["row"] == 2

    assert (
        quarantined["record"]["temperature_c"]
        == ""
    )

    assert len(quarantined["errors"]) == 1

    error = quarantined["errors"][0]

    assert error["type"] == "missing_value"
    assert error.get("column") == "temperature_c"
    assert error["message"] == "Missing value"
    assert error.get("invalid_value") == ""

def test_process_csv_duplicate_is_skipped():
    path = (
        Path(__file__).parent
        / "fixtures/process_duplicate_readings.csv"
    )

    result = process_csv(path)

    assert len(result["accepted"]) == 1
    assert result["quarantined"] == []

    assert result["skipped_duplicate_rows"] == [3]

def test_process_csv_conflict_quarantines_both_readings():
    path = (
        Path(__file__).parent
        / "fixtures/process_conflict_readings.csv"
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
        error["type"] == "conflict"
        and error.get("related_row") == 3
        for error in row_2["errors"]
    )

    assert any(
        error["type"] == "conflict"
        and error.get("related_row") == 2
        for error in row_3["errors"]
    )