"""Read-only connectivity probe for the isolated PostgreSQL test service.

This script is intentionally restricted to the Docker Compose test database.
It must never be used to probe the development or Airflow metadata databases.
"""

from __future__ import annotations

import logging
import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


log = logging.getLogger(__name__)


def validate_test_connection(
    url: str | None, expected_database: str | None, expected_user: str | None
) -> str:
    """Fail closed unless the destination matches the isolated test service."""
    if not url or not expected_database or not expected_user:
        raise ValueError("Missing test PostgreSQL connection configuration")

    config = conninfo_to_dict(url)
    if (
        config.get("host") != "postgres_test"
        or config.get("dbname") != expected_database
        or config.get("user") != expected_user
        or expected_database == os.getenv("POSTGRES_DB")
        or expected_user == os.getenv("POSTGRES_USER")
    ):
        raise ValueError(
            "Refusing connection: target must be the isolated postgres_test service"
        )
    return url


def probe_test_postgres() -> None:
    url = validate_test_connection(
        os.getenv("TEST_DATABASE_URL"),
        os.getenv("POSTGRES_TEST_DB"),
        os.getenv("POSTGRES_TEST_USER"),
    )
    with psycopg.connect(url, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user;")
            row = cursor.fetchone()

    if row != (os.environ["POSTGRES_TEST_DB"], os.environ["POSTGRES_TEST_USER"]):
        raise RuntimeError("Test database identity does not match configuration")

    log.info("Test PostgreSQL connectivity succeeded | service=postgres_test")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    probe_test_postgres()


if __name__ == "__main__":
    main()
