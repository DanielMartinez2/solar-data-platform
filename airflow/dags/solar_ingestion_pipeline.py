"""Orchestrate Solar Data Platform migrations, ingestion, and dbt build."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
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


def send_failure_email(context: dict) -> None:
    """Send one SMTP notification for a failed DAG run, if configured."""
    host = os.getenv("SOLAR_SMTP_HOST", "").strip()
    sender = os.getenv("SOLAR_ALERT_FROM", "").strip()
    recipient = os.getenv("SOLAR_ALERT_TO", "").strip()
    if not all((host, sender, recipient)):
        log.warning(
            "Failure email skipped: configure SOLAR_SMTP_HOST, "
            "SOLAR_ALERT_FROM and SOLAR_ALERT_TO."
        )
        return

    port = int(os.getenv("SOLAR_SMTP_PORT", "587"))
    username = os.getenv("SOLAR_SMTP_USERNAME", "")
    password = os.getenv("SOLAR_SMTP_PASSWORD", "")
    use_starttls = os.getenv("SOLAR_SMTP_STARTTLS", "true").lower() == "true"

    dag_id = context["dag"].dag_id
    run_id = context["run_id"]
    reason = str(context.get("reason") or context.get("exception") or "Not provided")
    message = EmailMessage()
    message["Subject"] = f"[Solar Data Platform] DAG failed: {dag_id}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"DAG: {dag_id}\nRun ID: {run_id}\nReason: {reason[:1000]}\n"
        "Inspect the Airflow UI and DAG processor logs for task details.\n"
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        # A notification problem must not mask the original DAG failure.
        log.error("Failure email could not be sent: %s", type(error).__name__)
    else:
        log.info("Failure email sent | dag_id=%s | run_id=%s", dag_id, run_id)


def log_dag_failure(context: dict) -> None:
    """Record failed DAG runs and optionally send one email alert."""
    log.error(
        "DAG run failed | dag_id=%s | run_id=%s | reason=%s",
        context["dag"].dag_id,
        context["run_id"],
        context.get("reason", "not provided"),
    )
    send_failure_email(context)


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
