"""Orchestrate Solar Data Platform migrations, ingestion, and dbt build."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
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

    started_at = time.perf_counter()
    try:
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        log.error(
            "Step failed: %s | exit_code=%s | duration_seconds=%.3f",
            description,
            error.returncode,
            time.perf_counter() - started_at,
        )
        raise
    else:
        log.info(
            "Step succeeded: %s | duration_seconds=%.3f",
            description,
            time.perf_counter() - started_at,
        )


def log_task_retry(context: dict) -> None:
    """Record retries in the DAG processor logs."""
    task_instance = context["task_instance"]
    log.warning(
        "Task retry | dag_id=%s | task_id=%s | run_id=%s | try_number=%s",
        task_instance.dag_id,
        task_instance.task_id,
        context["run_id"],
        task_instance.try_number,
    )


def log_task_failure(context: dict) -> None:
    """Record terminal task failures in the DAG processor logs."""
    task_instance = context["task_instance"]
    log.error(
        "Task failed | dag_id=%s | task_id=%s | run_id=%s | try_number=%s | exception=%s",
        task_instance.dag_id,
        task_instance.task_id,
        context["run_id"],
        task_instance.try_number,
        context.get("exception"),
    )


def log_dag_failure(context: dict) -> None:
    """Record failed DAG runs, including run-level timeout failures."""
    log.error(
        "DAG run failed | dag_id=%s | run_id=%s | reason=%s",
        context["dag"].dag_id,
        context["run_id"],
        context.get("reason", "not provided"),
    )


@dag(
    dag_id="solar_ingestion_pipeline",
    schedule="0 9 * * *",
    start_date=pendulum.datetime(2026, 10, 29, 9, 0, tz="America/Sao_Paulo"),
    catchup=False,
    default_args={
        "on_retry_callback": log_task_retry,
        "on_failure_callback": log_task_failure,
    },
    on_failure_callback=log_dag_failure,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=20),
    tags=["solar-data-platform", "ingestion"],
)
def solar_ingestion_pipeline():
    """Run migrations, ingest available CSV batches, then build dbt models."""

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
        run_checked(
            [sys.executable, "-m", "scripts.ingest_raw_batches"],
            "Discovering and incrementally ingesting raw CSV batches.",
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
