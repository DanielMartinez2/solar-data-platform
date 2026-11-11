"""Execute the intentional dbt quality test against isolated PostgreSQL only."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
from pathlib import Path

from scripts.probe_test_postgres import validate_test_connection

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT = PROJECT_ROOT / "scripts" / "dbt_resilience"
log = logging.getLogger(__name__)


def build_command(allow_pass: bool) -> tuple[list[str], dict[str, str]]:
    """Validate isolated target before constructing the dbt test command."""
    validate_test_connection(
        os.getenv("TEST_DATABASE_URL"),
        os.getenv("POSTGRES_TEST_DB"),
        os.getenv("POSTGRES_TEST_USER"),
    )
    if not os.getenv("DBT_ENV_SECRET_TEST_POSTGRES_PASSWORD"):
        raise ValueError("Missing isolated dbt test password")

    environment = os.environ.copy()
    environment["DBT_RESILIENCE_FORCE_FAILURE"] = "false" if allow_pass else "true"
    command = [
        "dbt", "test",
        "--project-dir", str(DBT_PROJECT),
        "--profiles-dir", str(DBT_PROJECT),
        "--select", "intentional_quality_failure",
    ]
    return command, environment


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated dbt test failure drill")
    parser.add_argument(
        "--allow-pass", action="store_true",
        help="Make the singular dbt test return zero failing records",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    command, env = build_command(args.allow_pass)
    log.info(
        "Running isolated dbt quality drill | expected_outcome=%s | target=postgres_test",
        "pass" if args.allow_pass else "fail",
    )
    completed = subprocess.run(command, env=env, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        log.error("dbt quality drill failed | exit_code=%s", completed.returncode)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
