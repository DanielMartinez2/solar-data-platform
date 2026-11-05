"""Unit tests for Airflow child-process severity forwarding, without Airflow DB."""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "airflow"
    / "dags"
    / "subprocess_logging.py"
)
spec = importlib.util.spec_from_file_location("solar_subprocess_logging", MODULE_PATH)
assert spec is not None and spec.loader is not None
subprocess_logging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subprocess_logging)


def test_forward_line_preserves_python_severity(caplog):
    with caplog.at_level(logging.DEBUG, logger=subprocess_logging.log.name):
        subprocess_logging.forward_line("INFO - Checking CSV batch\n")
        subprocess_logging.forward_line("WARNING - Batch quality warning\n")
        subprocess_logging.forward_line("ERROR - Ingestion failed\n")

    assert [(r.levelname, r.message) for r in caplog.records] == [
        ("INFO", "Checking CSV batch"),
        ("WARNING", "Batch quality warning"),
        ("ERROR", "Ingestion failed"),
    ]


def test_forward_line_does_not_change_unstructured_output(caplog):
    with caplog.at_level(logging.INFO, logger=subprocess_logging.log.name):
        subprocess_logging.forward_line("Running with dbt=1.9.0\n")
        subprocess_logging.forward_line("\n")

    assert [(r.levelname, r.message) for r in caplog.records] == [
        ("INFO", "Running with dbt=1.9.0")
    ]


def test_run_checked_streams_child_stderr_and_stdout(caplog, tmp_path):
    code = (
        "import sys; "
        "print('stdout event', flush=True); "
        "print('INFO - accepted', file=sys.stderr, flush=True); "
        "print('WARNING - quarantine limit', file=sys.stderr, flush=True)"
    )
    with caplog.at_level(logging.INFO, logger=subprocess_logging.log.name):
        subprocess_logging.run_checked(
            [sys.executable, "-c", code], "testing child logs", tmp_path
        )

    messages = [(r.levelname, r.message) for r in caplog.records]
    assert ("INFO", "stdout event") in messages
    assert ("INFO", "accepted") in messages
    assert ("WARNING", "quarantine limit") in messages
    assert any("Step succeeded:" in msg for _, msg in messages)


def test_run_checked_propagates_nonzero_exit(caplog, tmp_path):
    with caplog.at_level(logging.INFO, logger=subprocess_logging.log.name):
        with pytest.raises(subprocess.CalledProcessError) as exc:
            subprocess_logging.run_checked(
                [sys.executable, "-c", "import sys; sys.exit(7)"],
                "expected failure",
                tmp_path,
            )

    assert exc.value.returncode == 7
    assert any(
        r.levelno == logging.ERROR and "exit_code=7" in r.message
        for r in caplog.records
    )
