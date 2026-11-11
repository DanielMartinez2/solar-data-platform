"""Unit tests for bounded, side-effect-free resilience drill helpers."""

import importlib.util
import logging
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "airflow" / "dags" / "resilience_drill_helpers.py"
)
spec = importlib.util.spec_from_file_location("resilience_drill_helpers_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


@pytest.mark.parametrize("seconds", [0, -1, 121, 1.5, "5", True])
def test_rejects_unbounded_and_noninteger_sleep(seconds):
    with pytest.raises(ValueError, match="seconds must be"):
        helpers.hold_for_seconds(
            seconds, scenario="concurrency", run_id="manual__test",
        )


def test_rejects_unknown_scenario():
    with pytest.raises(ValueError, match="unknown resilience scenario"):
        helpers.hold_for_seconds(1, scenario="other", run_id="manual__test")


def test_rejects_missing_run_id():
    with pytest.raises(ValueError, match="run_id must not be empty"):
        helpers.hold_for_seconds(1, scenario="timeout", run_id="")


def test_logs_start_and_completion_without_real_wait(monkeypatch, caplog):
    sleeps = []
    monkeypatch.setattr(helpers.time, "sleep", lambda s: sleeps.append(s))
    with caplog.at_level(logging.INFO, logger=helpers.log.name):
        helpers.hold_for_seconds(
            45, scenario="concurrency", run_id="manual__example",
        )
    assert sleeps == [45]
    assert "Resilience drill started" in caplog.text
    assert "Resilience drill completed" in caplog.text
    assert "run_id=manual__example" in caplog.text
