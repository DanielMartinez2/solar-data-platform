"""Manual, read-only PostgreSQL test-service recovery drill.

This DAG is deliberately separate from the production ingestion pipeline.
It has no schedule and never writes to the solar development database.
"""

from __future__ import annotations

import logging
import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, task
from subprocess_logging import run_checked


log = logging.getLogger(__name__)
PROJECT_ROOT = Path("/opt/solar-data-platform")
PROBE = PROJECT_ROOT / "scripts" / "probe_test_postgres.py"


def log_retry(context: dict) -> None:
    ti = context["task_instance"]
    log.warning(
        "PostgreSQL recovery probe retry | task_id=%s | run_id=%s | try_number=%s",
        ti.task_id, context["run_id"], ti.try_number,
    )


@dag(
    dag_id="learning_postgres_recovery",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 29, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=5),
    tags=["learning", "resilience", "postgresql"],
)
def learning_postgres_recovery():
    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(seconds=20),
        on_retry_callback=log_retry,
    )
    def probe_test_database() -> None:
        if not PROBE.is_file():
            raise FileNotFoundError(f"Test PostgreSQL probe not found: {PROBE}")
        run_checked(
            [sys.executable, str(PROBE)],
            "Probing isolated PostgreSQL test service (read-only).",
            PROJECT_ROOT,
        )

    probe_test_database()


learning_postgres_recovery()
