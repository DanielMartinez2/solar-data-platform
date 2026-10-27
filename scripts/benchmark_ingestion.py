"""Measure ingestion phase timings without persisting benchmark data.

The benchmark uses a single database transaction and always rolls it back.
By default it connects through TEST_DATABASE_URL so development data is not
used accidentally.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import (  # noqa: E402
    finish_ingestion_run_success,
    insert_quarantined_readings,
    insert_readings,
    insert_readings_executemany,
)
from src.validate_readings import process_csv  # noqa: E402


@dataclass(frozen=True)
class BenchmarkResult:
    strategy: str
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


@dataclass(frozen=True)
class TimingStats:
    minimum: float
    maximum: float
    average: float
    median: float


def summarize_timings(values: list[float]) -> TimingStats:
    if not values:
        raise ValueError("At least one timing value is required")

    return TimingStats(
        minimum=min(values),
        maximum=max(values),
        average=mean(values),
        median=median(values),
    )


def validate_consistent_results(
    results: list[BenchmarkResult],
) -> None:
    if not results:
        raise ValueError("At least one benchmark result is required")

    expected_counts = (
        results[0].accepted_count,
        results[0].inserted_readings_count,
        results[0].quarantined_count,
        results[0].inserted_quarantined_count,
        results[0].duplicate_count,
    )

    for result in results[1:]:
        observed_counts = (
            result.accepted_count,
            result.inserted_readings_count,
            result.quarantined_count,
            result.inserted_quarantined_count,
            result.duplicate_count,
        )

        if observed_counts != expected_counts:
            raise RuntimeError(
                "Benchmark runs produced inconsistent row counts"
            )


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
    *,
    strategy: str,
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

        if strategy == "executemany":
            inserted_readings = insert_readings_executemany(
                result["accepted"],
                connection=connection,
            )
        elif strategy == "copy-staging":
            inserted_readings = insert_readings(
                result["accepted"],
                connection=connection,
            )
        else:
            raise ValueError(
                f"Unsupported benchmark strategy: {strategy}"
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
        strategy=strategy,
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
    print(f"Strategy: {result.strategy}")
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
        "  Accepted persistence:   "
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


def print_timing_stats(
    label: str,
    stats: TimingStats,
) -> None:
    print(
        f"{label:<24}"
        f"{stats.minimum:10.3f}"
        f"{stats.median:10.3f}"
        f"{stats.average:10.3f}"
        f"{stats.maximum:10.3f}"
    )


def print_summary(
    csv_path: Path,
    results: list[BenchmarkResult],
) -> None:
    validate_consistent_results(results)

    first = results[0]

    print()
    print("Ingestion benchmark summary")
    print("=" * 72)
    print(f"CSV: {csv_path}")
    print(f"Strategy: {first.strategy}")
    print(f"Runs: {len(results)}")
    print()
    print("Rows per run")
    print(f"  Accepted:              {first.accepted_count}")
    print(f"  Inserted readings:     {first.inserted_readings_count}")
    print(f"  Quarantined:           {first.quarantined_count}")
    print(
        "  Inserted quarantined:  "
        f"{first.inserted_quarantined_count}"
    )
    print(f"  Source duplicates:     {first.duplicate_count}")
    print()
    print("Timing statistics (seconds)")
    print(
        f"{'Phase':<24}"
        f"{'Min':>10}"
        f"{'Median':>10}"
        f"{'Mean':>10}"
        f"{'Max':>10}"
    )
    print("-" * 64)

    phases = [
        (
            "CSV classification",
            [item.classification_seconds for item in results],
        ),
        (
            "Accepted persistence",
            [item.accepted_insert_seconds for item in results],
        ),
        (
            "Quarantine INSERTs",
            [item.quarantine_insert_seconds for item in results],
        ),
        (
            "Audit finalization",
            [item.audit_finalize_seconds for item in results],
        ),
        (
            "Total",
            [item.total_seconds for item in results],
        ),
    ]

    for label, values in phases:
        print_timing_stats(
            label,
            summarize_timings(values),
        )

    print()
    print(
        "Use the median as the primary comparison metric between "
        "persistence strategies."
    )
    print("Database changes were rolled back after every run.")


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
        "--strategy",
        choices=("executemany", "copy-staging"),
        default="copy-staging",
        help=(
            "Accepted-reading persistence strategy. "
            "copy-staging is the production implementation; "
            "executemany is retained for comparison."
        ),
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help=(
            "Number of benchmark repetitions (default: 1). "
            "Use multiple runs to compare median timings."
        ),
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

    if args.runs < 1:
        raise ValueError("--runs must be at least 1")

    database_url = os.getenv(args.database_url_env)

    if not database_url:
        raise RuntimeError(
            f"Missing database URL in {args.database_url_env}"
        )

    results: list[BenchmarkResult] = []

    for run_number in range(1, args.runs + 1):
        result = benchmark_ingestion(
            csv_path,
            database_url,
            strategy=args.strategy,
        )
        results.append(result)

        if args.runs == 1:
            print_result(
                csv_path,
                result,
            )
        else:
            print(
                f"Run {run_number:>2}/{args.runs}: "
                f"accepted={result.accepted_insert_seconds:.3f} s, "
                f"total={result.total_seconds:.3f} s"
            )

    if args.runs > 1:
        print_summary(
            csv_path,
            results,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
