"""Orchestrate Solar Data Platform migrations and raw CSV ingestion."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from airflow.sdk import dag, task


log = logging.getLogger(__name__)

PROJECT_ROOT = Path("/opt/solar-data-platform")
MIGRATION_SCRIPT = PROJECT_ROOT / "scripts" / "run_migrations.py"


def run_checked(command: list[str], description: str) -> None:
    """Run a project command and fail the task if the command fails."""
    log.info("%s", description)
    log.info("Command: %s", " ".join(command))

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
    )


@dag(
    dag_id="solar_ingestion_pipeline",
    schedule=None,
    catchup=False,
    tags=["solar-data-platform", "ingestion"],
)
def solar_ingestion_pipeline():
    """Run schema migrations before ingesting the raw solar CSV."""

    @task
    def run_migrations() -> None:
        if not MIGRATION_SCRIPT.is_file():
            raise FileNotFoundError(
                f"Migration runner not found: {MIGRATION_SCRIPT}"
            )

        run_checked(
            [sys.executable, str(MIGRATION_SCRIPT)],
            "Running Solar Data Platform migrations.",
        )

    @task
    def ingest_raw_csv() -> None:
        raw_csv = PROJECT_ROOT / "data" / "raw" / "solar_readings.csv"

        if not raw_csv.is_file():
            raise FileNotFoundError(
                f"Raw solar CSV not found: {raw_csv}"
            )

        run_checked(
            [sys.executable, "-m", "src.database"],
            "Ingesting the raw solar CSV.",
        )

    run_migrations() >> ingest_raw_csv()


solar_ingestion_pipeline()
