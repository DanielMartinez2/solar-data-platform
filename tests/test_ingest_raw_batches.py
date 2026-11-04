"""Unit tests for batch discovery and incremental orchestration."""

from pathlib import Path

import pytest

from scripts import ingest_raw_batches


def test_discover_csv_batches_sorts_and_ignores_other_files(tmp_path: Path):
    (tmp_path / "b.csv").write_text("test", encoding="utf-8")
    (tmp_path / "a.csv").write_text("test", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("test", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "hidden.csv").write_text("test", encoding="utf-8")

    assert [item.name for item in ingest_raw_batches.discover_csv_batches(tmp_path)] == [
        "a.csv",
        "b.csv",
    ]


def test_discover_csv_batches_requires_input_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="No CSV batches found"):
        ingest_raw_batches.discover_csv_batches(tmp_path)


def test_discover_csv_batches_requires_directory(tmp_path: Path):
    with pytest.raises(NotADirectoryError, match="Raw data directory not found"):
        ingest_raw_batches.discover_csv_batches(tmp_path / "missing")


def test_ingest_batches_tracks_processed_and_skipped(tmp_path: Path, monkeypatch):
    for filename in ("a.csv", "b.csv", "c.csv"):
        (tmp_path / filename).write_text("test", encoding="utf-8")

    seen = []

    def fake_ingest(path: Path):
        seen.append(path.name)
        if path.name == "b.csv":
            return None
        return (
            {"accepted": [], "quarantined": [], "skipped_duplicate_rows": []},
            0,
            0,
        )

    monkeypatch.setattr(ingest_raw_batches, "ingest_csv_incremental", fake_ingest)

    assert ingest_raw_batches.ingest_batches(tmp_path) == (2, 1)
    assert seen == ["a.csv", "b.csv", "c.csv"]


def test_ingest_batches_stops_on_first_failure(tmp_path: Path, monkeypatch):
    for filename in ("a.csv", "b.csv", "c.csv"):
        (tmp_path / filename).write_text("test", encoding="utf-8")

    seen = []

    def fail_second(path: Path):
        seen.append(path.name)
        if path.name == "b.csv":
            raise RuntimeError("bad batch")
        return None

    monkeypatch.setattr(ingest_raw_batches, "ingest_csv_incremental", fail_second)

    with pytest.raises(RuntimeError, match="bad batch"):
        ingest_raw_batches.ingest_batches(tmp_path)

    assert seen == ["a.csv", "b.csv"]
