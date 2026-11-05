"""Forward subprocess output to Airflow at the original Python log level.

The subprocess typically writes its Python logging to stderr. Airflow may
otherwise label every line ERROR regardless of the actual message level.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path


log = logging.getLogger(__name__)
PYTHON_LOG_LINE = re.compile(r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL) - (.*)$")
LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def forward_line(line: str) -> None:
    """Forward known Python logging messages, leaving other tool output intact."""
    message = line.rstrip("\r\n")
    if not message:
        return

    match = PYTHON_LOG_LINE.match(message)
    if match:
        level, body = match.groups()
        log.log(LEVELS[level], "%s", body)
    else:
        # dbt, migrations and tracebacks are unstructured output.
        log.info("%s", message)


def run_checked(
    command: list[str], description: str, project_root: Path
) -> None:
    """Stream child logs and keep non-zero subprocess status fatal."""
    log.info("%s", description)
    log.info("Command: %s", " ".join(command))

    started_at = time.perf_counter()
    try:
        with subprocess.Popen(
            command,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                forward_line(line)
            exit_code = process.wait()

        if exit_code != 0:
            raise subprocess.CalledProcessError(exit_code, command)
    except subprocess.CalledProcessError as error:
        log.error(
            "Step failed: %s | exit_code=%s | duration_seconds=%.3f",
            description,
            error.returncode,
            time.perf_counter() - started_at,
        )
        raise
    else:
        log.info(
            "Step succeeded: %s | duration_seconds=%.3f",
            description,
            time.perf_counter() - started_at,
        )
