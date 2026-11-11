"""Unit tests for the isolated dbt quality-failure runner."""

import pytest

from scripts import run_dbt_resilience


def test_command_defaults_to_intentional_failure(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql://solar_test_user:pw@postgres_test:5432/solar_data_test",
    )
    monkeypatch.setenv("POSTGRES_TEST_DB", "solar_data_test")
    monkeypatch.setenv("POSTGRES_TEST_USER", "solar_test_user")
    monkeypatch.setenv("POSTGRES_DB", "solar_data")
    monkeypatch.setenv("POSTGRES_USER", "solar_user")
    monkeypatch.setenv("DBT_ENV_SECRET_TEST_POSTGRES_PASSWORD", "pw")

    command, env = run_dbt_resilience.build_command(allow_pass=False)
    assert command[:2] == ["dbt", "test"]
    assert command[-1] == "intentional_quality_failure"
    assert env["DBT_RESILIENCE_FORCE_FAILURE"] == "true"

    _, passing_env = run_dbt_resilience.build_command(allow_pass=True)
    assert passing_env["DBT_RESILIENCE_FORCE_FAILURE"] == "false"


def test_command_rejects_development_database(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql://solar_test_user:pw@postgres:5432/solar_data_test",
    )
    monkeypatch.setenv("POSTGRES_TEST_DB", "solar_data_test")
    monkeypatch.setenv("POSTGRES_TEST_USER", "solar_test_user")
    monkeypatch.setenv("POSTGRES_DB", "solar_data")
    monkeypatch.setenv("POSTGRES_USER", "solar_user")
    monkeypatch.setenv("DBT_ENV_SECRET_TEST_POSTGRES_PASSWORD", "pw")

    with pytest.raises(ValueError, match="Refusing connection"):
        run_dbt_resilience.build_command(False)


def test_command_requires_isolated_password(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql://solar_test_user:pw@postgres_test:5432/solar_data_test",
    )
    monkeypatch.setenv("POSTGRES_TEST_DB", "solar_data_test")
    monkeypatch.setenv("POSTGRES_TEST_USER", "solar_test_user")
    monkeypatch.setenv("POSTGRES_DB", "solar_data")
    monkeypatch.setenv("POSTGRES_USER", "solar_user")
    monkeypatch.delenv("DBT_ENV_SECRET_TEST_POSTGRES_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="Missing isolated dbt test password"):
        run_dbt_resilience.build_command(False)
