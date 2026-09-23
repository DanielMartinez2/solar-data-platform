"""Unit tests for the standalone synthetic-solar-data generator."""
import csv
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from scripts.generate_solar_data import Config, generate


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_small_run_without_anomalies_has_expected_rows(tmp_path: Path):
    target = tmp_path / "simple.csv"
    config = Config(days=1, interval_minutes=60, sites=2,
                    panels_per_site=2, gap_pct=0, duplicate_pct=0,
                    invalid_pct=0, output=target)
    report = generate(config)
    rows = load_rows(target)

    assert config.expected_rows == 96
    assert len(rows) == 96
    assert len({(r["timestamp"], r["site_id"], r["panel_id"]) for r in rows}) == 96
    assert all("+00:00" in row["timestamp"] for row in rows)
    assert all(float(row["irradiance_wm2"]) >= 0 for row in rows)
    assert report["counts"]["written_csv_rows"] == 96
    assert target.with_suffix(".manifest.json").exists()


def test_anomaly_rates_are_exact_and_categories_are_disjoint(tmp_path: Path):
    target = tmp_path / "anomalies.csv"
    config = Config(days=1, interval_minutes=60, sites=2, panels_per_site=2,
                    gap_pct=10, duplicate_pct=5, invalid_pct=5,
                    conflict_pct=5, output=target)
    report = generate(config)
    counts = report["counts"]
    rows = load_rows(target)
    assert counts == {
        "expected_measurements": 96,
        "gap_rows": 10,
        "invalid_rows": 5,
        "exact_duplicate_rows": 5,
        "conflict_extra_rows": 5,
        "written_csv_rows": 96,
    }
    assert len(rows) == 96

    # Each source measurement has exactly one natural key.
    # Extra records either match the original exactly or conflict with it.
    by_key: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row["timestamp"], row["site_id"], row["panel_id"])
        by_key.setdefault(key, []).append(row)

    assert len(by_key) == 86  # 96 planned - 10 gaps
    duplicates = [group for group in by_key.values()
                  if len(group) == 2 and group[0] == group[1]]
    conflicts = [group for group in by_key.values()
                 if len(group) == 2 and group[0] != group[1]]
    assert len(duplicates) == 5
    assert len(conflicts) == 5

    # Invalid records are disjoint from duplicate and conflict groups.
    invalid = [group for group in by_key.values()
               if group[0]["temperature_c"] == ""
               or float(group[0]["irradiance_wm2"]) < 0
               or group[0]["voltage_v"] == "invalid"]
    assert len(invalid) == 5
    assert all(len(group) == 1 for group in invalid)


def test_same_seed_produces_identical_csv(tmp_path: Path):
    config = Config(start_date=date(2026, 8, 1), days=2,
                    interval_minutes=30, sites=2, panels_per_site=2,
                    seed=123, gap_pct=2, duplicate_pct=1, invalid_pct=1,
                    conflict_pct=1, output=tmp_path / "a.csv")
    first = generate(config)
    second = generate(replace(config, output=tmp_path / "b.csv"))
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()
    assert first["csv_sha256"] == second["csv_sha256"]


def test_refuses_to_overwrite_existing_dataset(tmp_path: Path):
    config = Config(days=1, interval_minutes=60, sites=1,
                    panels_per_site=1, output=tmp_path / "existing.csv")
    generate(config)
    before = config.output_path.read_bytes()
    with pytest.raises(FileExistsError):
        generate(config)
    assert config.output_path.read_bytes() == before


@pytest.mark.parametrize("frequency", [0, 7, 1441])
def test_rejects_invalid_frequency(frequency: int):
    with pytest.raises(ValueError):
        Config(interval_minutes=frequency).validate()


def test_rejects_excessive_anomaly_percentages():
    with pytest.raises(ValueError):
        Config(gap_pct=60, duplicate_pct=50).validate()


def test_default_parameters_generate_288000_planned_measurements():
    config = Config()
    assert config.expected_rows == 288_000
    assert config.sites * config.panels_per_site == 100


def test_night_zero_and_midday_positive_irradiance(tmp_path: Path):
    target = tmp_path / "diurnal.csv"
    generate(Config(days=1, interval_minutes=60, sites=1,
                    panels_per_site=1, gap_pct=0, duplicate_pct=0,
                    invalid_pct=0, output=target))
    rows = load_rows(target)
    # Local midnight is 03:00 UTC with the simulator's fixed UTC-3 timezone.
    assert rows[0]["timestamp"].endswith("03:00:00+00:00")
    assert float(rows[0]["irradiance_wm2"]) == 0
    assert float(rows[0]["current_a"]) == 0
    assert float(rows[12]["irradiance_wm2"]) > 100
    assert float(rows[12]["voltage_v"]) > 0


def test_manifest_contains_model_and_checksum(tmp_path: Path):
    target = tmp_path / "manifest_test.csv"
    manifest = generate(Config(days=1, interval_minutes=60, sites=1,
                               panels_per_site=1, output=target))
    assert manifest["panel_model"]["model"] == "CS6W-550MS"
    assert len(manifest["csv_sha256"]) == 64
    assert manifest["counts"]["expected_measurements"] == 24
