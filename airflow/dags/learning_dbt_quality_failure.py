"""Manually exercise dbt quality failure propagation and a later passing run.

Isolated from solar_ingestion_pipeline; runs only the standalone dbt fixture.
"""

from __future__ import annotations

import logging
import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, get_current_context, task
from subprocess_logging import run_checked


log = logging.getLogger(__name__)
PROJECT_ROOT = Path("/opt/solar-data-platform")


def log_retry(context: dict) -> None:
    task_instance = context["task_instance"]
    log.warning(
        "dbt quality drill retry | task_id=%s | run_id=%s | try_number=%s",
        task_instance.task_id, context["run_id"], task_instance.try_number,
    )


@dag(
    dag_id="learning_dbt_quality_failure",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 29, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=6),
    tags=["learning", "resilience", "dbt"],
)
def learning_dbt_quality_failure():
    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(minutes=1),
        on_retry_callback=log_retry,
    )
    def run_isolated_quality_test() -> None:
        context = get_current_context()
        conf = context["dag_run"].conf or {}
        # Deliberate failure is the default. A passing run requires explicit opt-in.
        allow_pass = conf.get("allow_pass", False)
        if not isinstance(allow_pass, bool):
            raise ValueError("DAG run configuration allow_pass must be boolean")

        command = [sys.executable, "-m", "scripts.run_dbt_resilience"]
        if allow_pass:
            command.append("--allow-pass")
        log.info(
            "dbt quality drill | mode=%s | isolated_service=postgres_test",
            "pass" if allow_pass else "intentional_failure",
        )
        run_checked(
            command,
            "Executing isolated dbt quality test.",
            PROJECT_ROOT,
        )

    run_isolated_quality_test()


learning_dbt_quality_failure()
