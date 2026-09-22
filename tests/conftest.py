
import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

INTEGRATION_TEST_FILES = {
    "test_database.py",
    "test_pipeline_integration.py",
}


def pytest_collection_modifyitems(
    items: list[pytest.Item],
) -> None:
    has_integration_tests = any(
        item.path.name in INTEGRATION_TEST_FILES
        for item in items
    )

    if not has_integration_tests:
        return

    test_url = os.getenv("TEST_DATABASE_URL")
    development_url = os.getenv("DATABASE_URL")

    expected_database = os.getenv("POSTGRES_TEST_DB")
    expected_user = os.getenv("POSTGRES_TEST_USER")
    expected_port = os.getenv("POSTGRES_TEST_PORT")

    if not all(
        [
            test_url,
            development_url,
            expected_database,
            expected_user,
            expected_port,
        ]
    ):
        raise pytest.UsageError(
            "Missing test database configuration in .env"
        )

    assert test_url is not None
    assert development_url is not None

    test_config = conninfo_to_dict(test_url)
    development_config = conninfo_to_dict(
        development_url
    )

    if (
        test_config.get("dbname") != expected_database
        or test_config.get("user") != expected_user
        or test_config.get("port") != expected_port
    ):
        raise pytest.UsageError(
            "TEST_DATABASE_URL does not match "
            "the configured test database"
        )

    test_target = (
        test_config.get("host"),
        test_config.get("port"),
        test_config.get("dbname"),
    )

    development_target = (
        development_config.get("host"),
        development_config.get("port"),
        development_config.get("dbname"),
    )

    if test_target == development_target:
        raise pytest.UsageError(
            "Test and development databases "
            "must be different"
        )

    try:
        with psycopg.connect(
            test_url,
            connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT current_database(), current_user;
                    """
                )

                identity = cursor.fetchone()

    except psycopg.Error as error:
        raise pytest.UsageError(
            "Could not connect to the test database"
        ) from error

    if identity != (
        expected_database,
        expected_user,
    ):
        raise pytest.UsageError(
            "Connected database identity "
            "does not match the test configuration"
        )

    # Existing database functions now use the test database.
    os.environ["DATABASE_URL"] = test_url