"""Read-only, bounded delays for manual Airflow scheduling drills."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


def hold_for_seconds(seconds: int, *, scenario: str, run_id: str) -> None:
    """Emit markers surrounding a bounded, side-effect-free sleep."""
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be an integer between 1 and 120")
    if scenario not in {"timeout", "concurrency"}:
        raise ValueError("unknown resilience scenario")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must not be empty")

    log.info(
        "Resilience drill started | scenario=%s | run_id=%s | hold_seconds=%s",
        scenario, run_id, seconds,
    )
    time.sleep(seconds)
    log.info(
        "Resilience drill completed | scenario=%s | run_id=%s | hold_seconds=%s",
        scenario, run_id, seconds,
    )
