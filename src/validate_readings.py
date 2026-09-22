import csv
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict, NotRequired


REQUIRED_COLUMNS = (
    "timestamp",
    "site_id",
    "panel_id",
    "irradiance_wm2",
    "temperature_c",
    "voltage_v",
    "current_a",
)


class MissingValueError(TypedDict):
    row: int
    column: str
    message: str


class DuplicateError(TypedDict):
    row: int
    related_row: int
    message: str


class ConflictError(TypedDict):
    row: int
    related_row: int
    message: str


class ConversionError(TypedDict):
    row: int
    column: str
    message: str
    invalid_value: str


class DomainViolationError(TypedDict):
    row: int
    column: str
    message: str
    invalid_value: str

class TimestampError(TypedDict):
    row: int
    column: str
    message: str
    invalid_value: str

class ValidationErrors(TypedDict):
    missing_value: list[MissingValueError]
    conversion_error: list[ConversionError]
    domain_violation: list[DomainViolationError]
    timestamp_error: list[TimestampError]
    duplicate: list[DuplicateError]
    conflict: list[ConflictError]


class AcceptedReading(TypedDict):
    timestamp: datetime
    site_id: str
    panel_id: str
    irradiance_wm2: float
    temperature_c: float
    voltage_v: float
    current_a: float

class QuarantineError(TypedDict):
    type: Literal[
        "missing_value",
        "conversion_error",
        "domain_violation",
        "timestamp_error",
        "conflict",
    ]
    message: str
    column: NotRequired[str]
    invalid_value: NotRequired[str]
    related_row: NotRequired[int]


class QuarantinedReading(TypedDict):
    row: int
    record: dict[str, str]
    errors: list[QuarantineError]


class IngestionResult(TypedDict):
    accepted: list[AcceptedReading]
    quarantined: list[QuarantinedReading]
    skipped_duplicate_rows: list[int]

type UniquenessResult = (
    tuple[Literal["new"], None]
    | tuple[Literal["duplicate"], int]
    | tuple[Literal["conflict"], int]
)


def count_errors(errors: ValidationErrors) -> int:
    total = 0

    for entries in errors.values():
        assert isinstance(entries, list)
        total += len(entries)

    return total


def build_natural_key(row: dict) -> tuple[str, str, str]:
    return (
        row["timestamp"],
        row["site_id"],
        row["panel_id"],
    )


def parse_numeric_value(value: str) -> float | None:
    if not value.strip():
        return None

    return float(value)


def validate_domain_rule(
    column: str,
    value: float,
) -> tuple[bool, str | None]:

    if column == "irradiance_wm2" and value < 0:
        return False, "Irradiance cannot be a negative value"

    return True, None


def check_reading_uniqueness(
    row: dict,
    seen_readings: dict,
) -> UniquenessResult:

    key = build_natural_key(row)

    if key not in seen_readings:
        return "new", None

    if seen_readings[key][1] == row:
        return "duplicate", seen_readings[key][0]

    return "conflict", seen_readings[key][0]


def normalize_reading(
    row: dict[str, str],
) -> AcceptedReading:

    timestamp = datetime.fromisoformat(row["timestamp"])

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(
            "Timestamp must include timezone information"
        )

    return {
        "timestamp": timestamp,
        "site_id": row["site_id"],
        "panel_id": row["panel_id"],
        "irradiance_wm2": float(row["irradiance_wm2"]),
        "temperature_c": float(row["temperature_c"]),
        "voltage_v": float(row["voltage_v"]),
        "current_a": float(row["current_a"]),
    }

def validate_timestamp(value: str) -> str | None:
    if not value.strip():
        return "Missing timestamp"

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return "Invalid timestamp format"

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return "Timestamp must include timezone information"

    return None

def validate_row_fields(
    row: dict[str, str],
) -> list[QuarantineError]:

    quarantine_errors: list[QuarantineError] = []

    # Timestamp
    timestamp_error = validate_timestamp(row["timestamp"])

    if timestamp_error is not None:
        quarantine_errors.append({
            "type": "timestamp_error",
            "column": "timestamp",
            "message": timestamp_error,
            "invalid_value": row["timestamp"],
        })

    # Numeric fields
    numeric_columns = (
        "irradiance_wm2",
        "temperature_c",
        "voltage_v",
        "current_a",
    )

    for column in numeric_columns:
        value = row[column]

        try:
            num = parse_numeric_value(value)

        except ValueError:
            quarantine_errors.append({
                "type": "conversion_error",
                "column": column,
                "message": "Conversion error",
                "invalid_value": value,
            })
            continue

        if num is None:
            quarantine_errors.append({
                "type": "missing_value",
                "column": column,
                "message": "Missing value",
                "invalid_value": value,
            })
            continue

        is_valid, error_message = validate_domain_rule(
            column,
            num,
        )

        if not is_valid:
            assert error_message is not None

            quarantine_errors.append({
                "type": "domain_violation",
                "column": column,
                "message": error_message,
                "invalid_value": value,
            })

    return quarantine_errors

def validate_csv(csv_path: Path) -> ValidationErrors:
    with open(
        csv_path,
        encoding="utf-8",
        newline="",
    ) as csvfile:

        reader = csv.DictReader(csvfile)
        columns = reader.fieldnames

        if columns is None:
            raise ValueError(
                "The CSV file has no header row."
            )

        missing_columns = set(REQUIRED_COLUMNS) - set(columns)

        if missing_columns:
            raise ValueError(
                f"Missing columns: {sorted(missing_columns)}"
            )

        numeric_columns = (
            "irradiance_wm2",
            "temperature_c",
            "voltage_v",
            "current_a",
        )

        errors: ValidationErrors = {
            "missing_value": [],
            "conversion_error": [],
            "domain_violation": [],
            "duplicate": [],
            "conflict": [],
            "timestamp_error": []
        }

        seen_readings = {}

        for index, row in enumerate(reader):
            row_number = index + 2

            timestamp_error = validate_timestamp(row["timestamp"])

            if timestamp_error is not None:
                errors["timestamp_error"].append({
                    "row": row_number,
                    "column": "timestamp",
                    "message": timestamp_error,
                    "invalid_value": row["timestamp"],
                })

            uniqueness_result = check_reading_uniqueness(
                row,
                seen_readings,
            )

            if uniqueness_result[0] == "new":
                seen_readings[build_natural_key(row)] = [
                    row_number,
                    row,
                ]

            elif uniqueness_result[0] == "duplicate":
                existing_row_number = uniqueness_result[1]

                errors["duplicate"].append({
                    "row": row_number,
                    "related_row": existing_row_number,
                    "message": "Duplicate reading",
                })

            elif uniqueness_result[0] == "conflict":
                existing_row_number = uniqueness_result[1]

                errors["conflict"].append({
                    "row": row_number,
                    "related_row": existing_row_number,
                    "message": "Conflicting reading",
                })

            for column in numeric_columns:
                value = row[column]

                try:
                    num = parse_numeric_value(value)

                except ValueError:
                    errors["conversion_error"].append({
                        "row": row_number,
                        "column": column,
                        "message": "Conversion error",
                        "invalid_value": value,
                    })
                    continue

                if num is None:
                    errors["missing_value"].append({
                        "row": row_number,
                        "column": column,
                        "message": "Missing value",
                    })
                    continue

                is_valid, error_message = validate_domain_rule(
                    column,
                    num,
                )

                if not is_valid:
                    assert error_message is not None

                    errors["domain_violation"].append({
                        "row": row_number,
                        "column": column,
                        "message": error_message,
                        "invalid_value": value,
                    })

    return errors

def process_csv(csv_path: Path) -> IngestionResult:
    accepted: list[AcceptedReading] = []
    quarantined: list[QuarantinedReading] = []
    skipped_duplicate_rows: list[int] = []

    with csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("CSV file has no header")

        missing_columns = (
            set(REQUIRED_COLUMNS)
            - set(reader.fieldnames)
        )

        if missing_columns:
            raise ValueError(
                f"Missing required columns: "
                f"{sorted(missing_columns)}"
            )

        grouped_rows: dict[
            tuple[str, str, str],
            list[tuple[int, dict[str, str]]],
        ] = {}

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            key = build_natural_key(row)

            grouped_rows.setdefault(
                key,
                [],
            ).append(
                (
                    row_number,
                    row,
                )
            )

    for rows in grouped_rows.values():
        distinct_records: dict[
            tuple[str, ...],
            tuple[int, dict[str, str]],
        ] = {}

        for row_number, row in rows:
            signature = build_record_signature(row)

            if signature in distinct_records:
                skipped_duplicate_rows.append(
                    row_number
                )
                continue

            distinct_records[signature] = (
                row_number,
                row,
            )

        representatives = list(
            distinct_records.values()
        )

        if len(representatives) == 1:
            row_number, row = representatives[0]

            row_errors = validate_row_fields(row)

            if row_errors:
                quarantined.append(
                    {
                        "row": row_number,
                        "record": dict(row),
                        "errors": row_errors,
                    }
                )
            else:
                accepted.append(
                    normalize_reading(row)
                )

            continue

        representative_rows = [
            row_number
            for row_number, _ in representatives
        ]

        for row_number, row in representatives:
            row_errors = validate_row_fields(row)

            conflict_errors: list[
                QuarantineError
            ] = []

            for related_row in representative_rows:
                if related_row == row_number:
                    continue

                conflict_errors.append(
                    {
                        "type": "conflict",
                        "message": (
                            "Conflicting reading for "
                            "the same natural key"
                        ),
                        "related_row": related_row,
                    }
                )

            quarantined.append(
                {
                    "row": row_number,
                    "record": dict(row),
                    "errors": (
                        row_errors
                        + conflict_errors
                    ),
                }
            )

    return {
        "accepted": accepted,
        "quarantined": quarantined,
        "skipped_duplicate_rows":
            skipped_duplicate_rows,
    }

def build_record_signature(
    row: dict[str, str],
) -> tuple[str, ...]:
    return tuple(
        row.get(column, "")
        for column in REQUIRED_COLUMNS
    )

def main():
    csv_path = (
        Path(__file__).parents[1]
        / "data/raw/solar_readings.csv"
    )

    '''errors = validate_csv(csv_path)
    num_errors = count_errors(errors)

    print(
        "Number of errors found in the CSV file:",
        num_errors,
    )

    for error_type, values in errors.items():
        if values:
            print(f"{error_type}: {values}")'''
    result = process_csv(csv_path)

    print("Accepted:", len(result["accepted"]))
    print("Quarantined:", len(result["quarantined"]))
    print(
        "Skipped duplicate rows:",
        result["skipped_duplicate_rows"],
    )

    for item in result["quarantined"]:
        print(
            item["row"],
            item["errors"],
        )


if __name__ == "__main__":
    main()