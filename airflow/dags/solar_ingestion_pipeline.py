"""Orchestrate Solar Data Platform migrations, ingestion, and dbt build."""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pendulum

from airflow.sdk import dag, task


log = logging.getLogger(__name__)

PROJECT_ROOT = Path("/opt/solar-data-platform")
MIGRATION_SCRIPT = PROJECT_ROOT / "scripts" / "run_migrations.py"
DBT_PROJECT_DIR = PROJECT_ROOT / "warehouse"


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
    schedule="0 9 * * *",
    start_date=pendulum.datetime(2026, 10, 29, 9, 0, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=20),
    tags=["solar-data-platform", "ingestion"],
)
def solar_ingestion_pipeline():
    """Run migrations, ingest the raw CSV, then build and test dbt models."""

    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(minutes=2),
    )
    def run_migrations() -> None:
        if not MIGRATION_SCRIPT.is_file():
            raise FileNotFoundError(
                f"Migration runner not found: {MIGRATION_SCRIPT}"
            )

        run_checked(
            [sys.executable, str(MIGRATION_SCRIPT)],
            "Running Solar Data Platform migrations.",
        )

    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(minutes=5),
    )
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

    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(minutes=10),
    )
    def dbt_build() -> None:
        dbt_project_file = DBT_PROJECT_DIR / "dbt_project.yml"
        profiles_file = DBT_PROJECT_DIR / "profiles.yml"

        if not dbt_project_file.is_file():
            raise FileNotFoundError(
                f"dbt project file not found: {dbt_project_file}"
            )

        if not profiles_file.is_file():
            raise FileNotFoundError(
                f"dbt profiles file not found: {profiles_file}"
            )

        run_checked(
            [
                "dbt",
                "build",
                "--project-dir",
                str(DBT_PROJECT_DIR),
                "--profiles-dir",
                str(DBT_PROJECT_DIR),
            ],
            "Building and testing the dbt warehouse.",
        )

    migrations_task = run_migrations()
    ingestion_task = ingest_raw_csv()
    dbt_task = dbt_build()

    migrations_task >> ingestion_task >> dbt_task


solar_ingestion_pipeline()
