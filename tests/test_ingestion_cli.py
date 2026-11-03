"""Tests for the ingestion CLI CSV path selection."""

from pathlib import Path

from src import database


def test_parse_args_uses_default_csv():
    args = database.parse_args([])

    assert args.csv_path == database.DEFAULT_CSV_PATH


def test_parse_args_accepts_explicit_csv_path(tmp_path):
    source = tmp_path / "new_batch.csv"

    args = database.parse_args(["--csv-path", str(source)])

    assert args.csv_path == source


def test_main_uses_explicit_csv_path(monkeypatch, tmp_path):
    source = tmp_path / "batch.csv"
    observed = []

    monkeypatch.setattr(
        "sys.argv", ["database", "--csv-path", str(source)]
    )

    def fake_ingest_csv(csv_path: Path):
        observed.append(csv_path)
        return (
            {"accepted": [], "quarantined": [], "skipped_duplicate_rows": []},
            0,
            0,
        )

    monkeypatch.setattr(database, "ingest_csv", fake_ingest_csv)

    database.main()

    assert observed == [source]


def test_parse_args_incremental_is_opt_in():
    assert database.parse_args([]).incremental is False
    args = database.parse_args(["--incremental", "--csv-path", "batch.csv"])
    assert args.incremental is True
    assert args.csv_path == Path("batch.csv")


def test_main_skips_without_unpacking_when_checkpoint_exists(monkeypatch, tmp_path, capsys):
    source = tmp_path / "already_processed.csv"
    monkeypatch.setattr(
        "sys.argv", ["database", "--incremental", "--csv-path", str(source)]
    )
    monkeypatch.setattr(database, "ingest_csv_incremental", lambda path: None)
    database.main()
    assert "Already processed: already_processed.csv" in capsys.readouterr().out
