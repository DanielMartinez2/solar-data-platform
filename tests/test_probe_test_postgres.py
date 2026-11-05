"""Unit tests for safe PostgreSQL recovery-drill connection validation."""

import pytest

from scripts.probe_test_postgres import validate_test_connection


TEST_URL = "postgresql://solar_test_user:secret@postgres_test:5432/solar_data_test"


def test_probe_allows_only_isolated_test_database(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "solar_data")
    monkeypatch.setenv("POSTGRES_USER", "solar_user")
    assert (
        validate_test_connection(
            TEST_URL, "solar_data_test", "solar_test_user"
        )
        == TEST_URL
    )


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://solar_test_user:secret@postgres:5432/solar_data_test",
        "postgresql://solar_test_user:secret@airflow-postgres:5432/solar_data_test",
        "postgresql://solar_user:secret@postgres_test:5432/solar_data_test",
        "postgresql://solar_test_user:secret@postgres_test:5432/solar_data",
    ],
)
def test_probe_rejects_non_test_target(monkeypatch, url):
    monkeypatch.setenv("POSTGRES_DB", "solar_data")
    monkeypatch.setenv("POSTGRES_USER", "solar_user")
    with pytest.raises(ValueError, match="Refusing connection"):
        validate_test_connection(url, "solar_data_test", "solar_test_user")


def test_probe_requires_complete_configuration():
    with pytest.raises(ValueError, match="Missing test"):
        validate_test_connection(None, "solar_data_test", "solar_test_user")


def test_probe_rejects_test_db_same_as_development(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "solar_data_test")
    monkeypatch.setenv("POSTGRES_USER", "solar_user")
    with pytest.raises(ValueError, match="Refusing connection"):
        validate_test_connection(TEST_URL, "solar_data_test", "solar_test_user")
