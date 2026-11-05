"""Discover immutable CSV batches and ingest them using file checkpoints.

Each file is independently checkpointed by src.database. A failed batch
stops this command with an error so Airflow does not continue to dbt.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.database import ingest_csv_incremental
from src.batch_quality_rules import check_batch_quality, load_thresholds


log = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def discover_csv_batches(data_dir: Path) -> list[Path]:
    """Return regular CSV files in a predictable order (no recursion)."""
    if not data_dir.is_dir():
        raise NotADirectoryError(f"Raw data directory not found: {data_dir}")

    batches = sorted(
        (path for path in data_dir.glob("*.csv") if path.is_file()),
        key=lambda path: path.name,
    )
    if not batches:
        raise FileNotFoundError(f"No CSV batches found in: {data_dir}")
    return batches


def ingest_batches(data_dir: Path) -> tuple[int, int]:
    """Process available batches; return (processed, skipped) counts."""
    processed = 0
    skipped = 0
    try:
        thresholds = load_thresholds()
    except ValueError:
        log.exception("Invalid quality thresholds; quality checks disabled for this run")
        thresholds = None

    for batch in discover_csv_batches(data_dir):
        log.info("Checking CSV batch | source_file=%s", batch.name)
        outcome = ingest_csv_incremental(batch)
        if outcome is None:
            skipped += 1
            log.info("CSV batch skipped | source_file=%s", batch.name)
        else:
            processed += 1
            result, inserted, inserted_quarantined = outcome
            log.info(
                "CSV batch processed | source_file=%s | accepted=%s | "
                "inserted=%s | quarantined=%s | quarantine_inserted=%s",
                batch.name,
                len(result["accepted"]),
                inserted,
                len(result["quarantined"]),
                inserted_quarantined,
            )
            if thresholds is not None:
                try:
                    check_batch_quality(batch.name, thresholds)
                except Exception:
                    # Quality monitoring must never mask a successful ingestion.
                    log.exception(
                        "Quality check unavailable | source_file=%s", batch.name
                    )

    log.info(
        "CSV batch discovery completed | processed=%s | skipped=%s | total=%s",
        processed,
        skipped,
        processed + skipped,
    )
    return processed, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover and incrementally ingest CSV batches."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing immutable CSV batches.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    ingest_batches(args.data_dir)


if __name__ == "__main__":
    main()
