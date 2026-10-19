"""Apply ordered PostgreSQL migrations for the Solar Data Platform."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import Connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"
MIGRATION_FILENAME = re.compile(
    r"^(?P<version>\d{3})_(?P<name>[a-z0-9][a-z0-9_]*)\.sql$"
)


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str
    sql: str

    @property
    def filename(self) -> str:
        return self.path.name


def migration_checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def discover_migrations(
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
) -> list[Migration]:
    if not migrations_dir.is_dir():
        raise FileNotFoundError(
            f"Migrations directory not found: {migrations_dir}"
        )

    migrations: list[Migration] = []
    versions: set[int] = set()

    for path in sorted(migrations_dir.glob("*.sql")):
        match = MIGRATION_FILENAME.fullmatch(path.name)

        if match is None:
            raise ValueError(
                "Invalid migration filename "
                f"{path.name!r}. Expected NNN_description.sql"
            )

        version = int(match.group("version"))

        if version in versions:
            raise ValueError(
                f"Duplicate migration version: {version:03d}"
            )

        sql = path.read_text(encoding="utf-8")

        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                path=path,
                checksum=migration_checksum(sql),
                sql=sql,
            )
        )
        versions.add(version)

    if not migrations:
        raise ValueError(
            f"No migration files found in {migrations_dir}"
        )

    return sorted(migrations, key=lambda item: item.version)


def ensure_tracking_table(
    connection: Connection[object],
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum VARCHAR(64) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def get_applied_migrations(
    connection: Connection[object],
) -> dict[int, tuple[str, str]]:
    rows = connection.execute(
        """
        SELECT version, name, checksum
        FROM schema_migrations
        ORDER BY version;
        """
    ).fetchall()

    return {
        int(version): (str(name), str(checksum))
        for version, name, checksum in rows
    }


def validate_applied_migrations(
    migrations: list[Migration],
    applied: dict[int, tuple[str, str]],
) -> None:
    migration_by_version = {
        migration.version: migration
        for migration in migrations
    }

    for version, (applied_name, applied_checksum) in applied.items():
        migration = migration_by_version.get(version)

        if migration is None:
            raise RuntimeError(
                "Database contains migration "
                f"{version:03d}, but the file is missing"
            )

        if migration.name != applied_name:
            raise RuntimeError(
                "Migration name mismatch for "
                f"{version:03d}: database={applied_name!r}, "
                f"file={migration.name!r}"
            )

        if migration.checksum != applied_checksum:
            raise RuntimeError(
                "Migration checksum mismatch for "
                f"{migration.filename}. Applied migrations "
                "must not be modified."
            )


def record_migration(
    connection: Connection[object],
    migration: Migration,
) -> None:
    connection.execute(
        """
        INSERT INTO schema_migrations (
            version,
            name,
            checksum
        )
        VALUES (%s, %s, %s);
        """,
        (
            migration.version,
            migration.name,
            migration.checksum,
        ),
    )


def baseline_existing_database(
    connection: Connection[object],
    migrations: list[Migration],
    applied: dict[int, tuple[str, str]],
    through_version: int,
) -> None:
    available_versions = {
        migration.version
        for migration in migrations
    }

    if through_version not in available_versions:
        raise ValueError(
            "Baseline version does not exist: "
            f"{through_version:03d}"
        )

    with connection.transaction():
        for migration in migrations:
            if migration.version > through_version:
                break

            if migration.version in applied:
                continue

            record_migration(connection, migration)
            print(f"BASELINE {migration.filename}")


def apply_pending_migrations(
    connection: Connection[object],
    migrations: list[Migration],
    applied: dict[int, tuple[str, str]],
) -> int:
    applied_count = 0

    for migration in migrations:
        if migration.version in applied:
            continue

        print(f"APPLY    {migration.filename}")

        with connection.transaction():
            connection.execute(migration.sql)
            record_migration(connection, migration)

        applied[migration.version] = (
            migration.name,
            migration.checksum,
        )
        applied_count += 1

    return applied_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply pending PostgreSQL migrations in numeric order."
        )
    )
    parser.add_argument(
        "--database-url-env",
        default="DATABASE_URL",
        help=(
            "Environment variable containing the PostgreSQL URL "
            "(default: DATABASE_URL)."
        ),
    )
    parser.add_argument(
        "--baseline-through",
        type=int,
        metavar="VERSION",
        help=(
            "Record migrations up to VERSION as already applied "
            "without executing them. Use only for a pre-existing "
            "database whose schema already matches those migrations."
        ),
    )
    return parser


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    args = build_parser().parse_args()
    database_url = os.getenv(args.database_url_env)

    if not database_url:
        raise RuntimeError(
            f"Missing database URL in {args.database_url_env}"
        )

    migrations = discover_migrations()

    with psycopg.connect(
        database_url,
        autocommit=True,
    ) as connection:
        ensure_tracking_table(connection)

        applied = get_applied_migrations(connection)
        validate_applied_migrations(migrations, applied)

        if args.baseline_through is not None:
            baseline_existing_database(
                connection,
                migrations,
                applied,
                args.baseline_through,
            )
            applied = get_applied_migrations(connection)
            validate_applied_migrations(migrations, applied)

        applied_count = apply_pending_migrations(
            connection,
            migrations,
            applied,
        )

    if applied_count == 0:
        print("Database is up to date.")
    else:
        print(
            f"Applied {applied_count} migration"
            f"{'s' if applied_count != 1 else ''}."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
