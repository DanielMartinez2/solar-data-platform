"""Run Solar Data Platform database migrations from Airflow."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from airflow.sdk import dag, task


log = logging.getLogger(__name__)

PROJECT_ROOT = Path("/opt/solar-data-platform")
MIGRATION_SCRIPT = PROJECT_ROOT / "scripts" / "run_migrations.py"


@dag(
    dag_id="solar_run_migrations",
    schedule=None,
    catchup=False,
    tags=["solar-data-platform", "database", "migrations"],
)
def solar_run_migrations():
    """Run the existing migration runner against the Solar PostgreSQL DB."""

    @task
    def run_migrations() -> None:
        if not MIGRATION_SCRIPT.is_file():
            raise FileNotFoundError(
                f"Migration runner not found: {MIGRATION_SCRIPT}"
            )

        command = [
            sys.executable,
            str(MIGRATION_SCRIPT),
        ]

        log.info("Running Solar Data Platform migrations.")
        log.info("Command: %s", " ".join(command))

        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
        )

        log.info("Solar Data Platform migrations completed successfully.")

    run_migrations()


solar_run_migrations()
