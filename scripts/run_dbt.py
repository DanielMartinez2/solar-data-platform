
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_ROOT = PROJECT_ROOT / "warehouse"

load_dotenv(PROJECT_ROOT / ".env")

# Reuse the existing PostgreSQL password and
# expose it as a protected dbt environment variable.
os.environ["DBT_ENV_SECRET_POSTGRES_PASSWORD"] = (
    os.environ["POSTGRES_PASSWORD"]
)


def main() -> int:
    command = [
        "dbt",
        *sys.argv[1:],
        "--profiles-dir",
        str(DBT_ROOT),
    ]

    return subprocess.call(
        command,
        cwd=DBT_ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())