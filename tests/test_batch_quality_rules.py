"""Tests for non-blocking data-quality warning rules."""

import logging

import pytest

from src.batch_quality_rules import (
    QualityThresholds,
    load_thresholds,
    quality_warnings,
)
from scripts import ingest_raw_batches


def test_quality_warnings_detect_all_three_rules():
    assert quality_warnings(0, 30.0, 15.0, QualityThresholds()) == [
        "empty_batch",
        "high_quarantine_rate",
        "high_duplicate_rate",
    ]


def test_quality_warnings_does_not_warn_at_threshold():
    assert quality_warnings(100, 20.0, 10.0, QualityThresholds()) == []


def test_quality_warnings_handles_null_rates_for_empty_batch():
    assert quality_warnings(0, None, None, QualityThresholds()) == [
        "empty_batch"
    ]


def test_load_thresholds_uses_environment(monkeypatch):
    monkeypatch.setenv("SOLAR_MAX_QUARANTINE_PCT", "25.5")
    monkeypatch.setenv("SOLAR_MAX_DUPLICATE_PCT", "4")
    assert load_thresholds() == QualityThresholds(25.5, 4.0)


@pytest.mark.parametrize("bad_value", ["NaN", "inf", "-1", "101", "oops"])
def test_load_thresholds_rejects_invalid_values(monkeypatch, bad_value):
    monkeypatch.setenv("SOLAR_MAX_DUPLICATE_PCT", bad_value)
    with pytest.raises(ValueError, match="SOLAR_MAX_DUPLICATE_PCT"):
        load_thresholds()


def test_quality_check_invoked_for_new_batch_only(tmp_path, monkeypatch):
    for name in ("a.csv", "b.csv"):
        (tmp_path / name).write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(ingest_raw_batches, "load_thresholds", QualityThresholds)
    monkeypatch.setattr(
        ingest_raw_batches,
        "ingest_csv_incremental",
        lambda path: None if path.name == "a.csv" else (
            {"accepted": [], "quarantined": [], "skipped_duplicate_rows": []},
            0, 0,
        ),
    )
    checked = []
    monkeypatch.setattr(
        ingest_raw_batches,
        "check_batch_quality",
        lambda name, thresholds: checked.append(name),
    )

    assert ingest_raw_batches.ingest_batches(tmp_path) == (1, 1)
    assert checked == ["b.csv"]


def test_quality_check_error_does_not_block_batch(tmp_path, monkeypatch, caplog):
    (tmp_path / "a.csv").write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(ingest_raw_batches, "load_thresholds", QualityThresholds)
    monkeypatch.setattr(
        ingest_raw_batches,
        "ingest_csv_incremental",
        lambda path: (
            {"accepted": [], "quarantined": [], "skipped_duplicate_rows": []},
            0, 0,
        ),
    )

    def fail_check(name, thresholds):
        raise RuntimeError("metrics unavailable")

    monkeypatch.setattr(ingest_raw_batches, "check_batch_quality", fail_check)
    with caplog.at_level(logging.ERROR):
        assert ingest_raw_batches.ingest_batches(tmp_path) == (1, 0)
    assert "Quality check unavailable" in caplog.text
