from pathlib import Path

import pytest

from scripts.run_migrations import (
    discover_migrations,
    migration_checksum,
)


def write_migration(
    directory: Path,
    filename: str,
    sql: str = "SELECT 1;\n",
) -> None:
    (directory / filename).write_text(
        sql,
        encoding="utf-8",
    )


def test_discover_migrations_orders_by_numeric_version(
    tmp_path: Path,
) -> None:
    write_migration(tmp_path, "003_third.sql")
    write_migration(tmp_path, "001_first.sql")
    write_migration(tmp_path, "002_second.sql")

    migrations = discover_migrations(tmp_path)

    assert [item.version for item in migrations] == [1, 2, 3]
    assert [item.name for item in migrations] == [
        "first",
        "second",
        "third",
    ]


def test_discover_migrations_rejects_invalid_filename(
    tmp_path: Path,
) -> None:
    write_migration(tmp_path, "migration_without_version.sql")

    with pytest.raises(ValueError, match="Invalid migration filename"):
        discover_migrations(tmp_path)


def test_discover_migrations_rejects_duplicate_version(
    tmp_path: Path,
) -> None:
    write_migration(tmp_path, "001_first.sql")
    write_migration(tmp_path, "001_another.sql")

    with pytest.raises(ValueError, match="Duplicate migration version"):
        discover_migrations(tmp_path)


def test_discover_migrations_requires_at_least_one_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="No migration files"):
        discover_migrations(tmp_path)


def test_migration_checksum_changes_with_sql_content() -> None:
    first = migration_checksum("SELECT 1;")
    second = migration_checksum("SELECT 2;")

    assert len(first) == 64
    assert first != second
