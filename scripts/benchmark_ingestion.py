"""Measure ingestion phase timings without persisting benchmark data.

The benchmark uses a single database transaction and always rolls it back.
By default it connects through TEST_DATABASE_URL so development data is not
used accidentally.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import psycopg
from dotenv import load_dotenv

from src.database import (
    finish_ingestion_run_success,
    insert_quarantined_readings,
    insert_readings,
)
from src.validate_readings import process_csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BenchmarkResult:
    classification_seconds: float
    accepted_insert_seconds: float
    quarantine_insert_seconds: float
    audit_finalize_seconds: float
    total_seconds: float
    accepted_count: int
    inserted_readings_count: int
    quarantined_count: int
    inserted_quarantined_count: int
    duplicate_count: int


def create_benchmark_run(
    connection: psycopg.Connection[Any],
    source_file: str,
) -> int:
    row = connection.execute(
        """
        INSERT INTO ingestion_runs (source_file)
        VALUES (%s)
        RETURNING id;
        """,
        (source_file,),
    ).fetchone()

    if row is None:
        raise RuntimeError("Could not create benchmark ingestion run")

    return int(row[0])


def clear_transaction_snapshot(
    connection: psycopg.Connection[Any],
) -> None:
    """Start from empty operational tables inside the rollback-only transaction."""

    connection.execute("DELETE FROM quarantined_readings;")
    connection.execute("DELETE FROM solar_readings;")
    connection.execute("DELETE FROM ingestion_runs;")


def benchmark_ingestion(
    csv_path: Path,
    database_url: str,
) -> BenchmarkResult:
    total_start = perf_counter()

    classification_start = perf_counter()
    result = process_csv(csv_path)
    classification_seconds = perf_counter() - classification_start

    with psycopg.connect(database_url) as connection:
        # These deletes are part of the same transaction and are rolled back
        # with the benchmark. They make repeated benchmark runs comparable.
        clear_transaction_snapshot(connection)

        run_id = create_benchmark_run(
            connection,
            csv_path.name,
        )

        accepted_start = perf_counter()
        inserted_readings = insert_readings(
            result["accepted"],
            connection=connection,
        )
        accepted_insert_seconds = perf_counter() - accepted_start

        quarantine_start = perf_counter()
        inserted_quarantined = insert_quarantined_readings(
            csv_path.name,
            result["quarantined"],
            connection=connection,
        )
        quarantine_insert_seconds = perf_counter() - quarantine_start

        audit_start = perf_counter()
        finish_ingestion_run_success(
            run_id,
            result,
            inserted_readings,
            inserted_quarantined,
            connection=connection,
        )
        audit_finalize_seconds = perf_counter() - audit_start

        total_seconds = perf_counter() - total_start

        # The benchmark must not change the database.
        connection.rollback()

    return BenchmarkResult(
        classification_seconds=classification_seconds,
        accepted_insert_seconds=accepted_insert_seconds,
        quarantine_insert_seconds=quarantine_insert_seconds,
        audit_finalize_seconds=audit_finalize_seconds,
        total_seconds=total_seconds,
        accepted_count=len(result["accepted"]),
        inserted_readings_count=inserted_readings,
        quarantined_count=len(result["quarantined"]),
        inserted_quarantined_count=inserted_quarantined,
        duplicate_count=len(result["skipped_duplicate_rows"]),
    )


def print_result(
    csv_path: Path,
    result: BenchmarkResult,
) -> None:
    print()
    print("Ingestion benchmark")
    print("=" * 72)
    print(f"CSV: {csv_path}")
    print()
    print("Rows")
    print(f"  Accepted:              {result.accepted_count}")
    print(f"  Inserted readings:     {result.inserted_readings_count}")
    print(f"  Quarantined:           {result.quarantined_count}")
    print(
        "  Inserted quarantined:  "
        f"{result.inserted_quarantined_count}"
    )
    print(f"  Source duplicates:     {result.duplicate_count}")
    print()
    print("Timings")
    print(
        "  CSV classification:    "
        f"{result.classification_seconds:10.3f} s"
    )
    print(
        "  Accepted INSERTs:       "
        f"{result.accepted_insert_seconds:10.3f} s"
    )
    print(
        "  Quarantine INSERTs:     "
        f"{result.quarantine_insert_seconds:10.3f} s"
    )
    print(
        "  Audit finalization:     "
        f"{result.audit_finalize_seconds:10.3f} s"
    )
    print("  " + "-" * 43)
    print(f"  Total:                  {result.total_seconds:10.3f} s")
    print()
    print("Database changes were rolled back.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the current ingestion implementation by phase. "
            "All benchmark database changes are rolled back."
        )
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="CSV file to benchmark.",
    )
    parser.add_argument(
        "--database-url-env",
        default="TEST_DATABASE_URL",
        help=(
            "Environment variable containing the PostgreSQL connection URL "
            "(default: TEST_DATABASE_URL)."
        ),
    )
    parser.add_argument(
        "--allow-development-database",
        action="store_true",
        help=(
            "Allow DATABASE_URL explicitly. The benchmark still rolls back "
            "its transaction, but the test database is preferred."
        ),
    )
    return parser


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    args = build_parser().parse_args()
    csv_path = args.csv_path.resolve()

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    if (
        args.database_url_env == "DATABASE_URL"
        and not args.allow_development_database
    ):
        raise RuntimeError(
            "Refusing to benchmark DATABASE_URL by default. "
            "Use TEST_DATABASE_URL or pass "
            "--allow-development-database explicitly."
        )

    database_url = os.getenv(args.database_url_env)

    if not database_url:
        raise RuntimeError(
            f"Missing database URL in {args.database_url_env}"
        )

    result = benchmark_ingestion(
        csv_path,
        database_url,
    )
    print_result(
        csv_path,
        result,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
