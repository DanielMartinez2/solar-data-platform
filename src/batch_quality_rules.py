"""Non-blocking quality checks for newly checkpointed CSV batches.

Metrics are read from vw_ingestion_batch_quality, keyed to the successful
ingestion run recorded in processed_files. Rules only emit log warnings.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass

from src.database import get_connection


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityThresholds:
    quarantine_pct: float = 20.0
    duplicate_pct: float = 10.0


def _percentage_from_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number between 0 and 100") from error
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f"{name} must be a finite number between 0 and 100")
    return value


def load_thresholds() -> QualityThresholds:
    return QualityThresholds(
        quarantine_pct=_percentage_from_env("SOLAR_MAX_QUARANTINE_PCT", 20.0),
        duplicate_pct=_percentage_from_env("SOLAR_MAX_DUPLICATE_PCT", 10.0),
    )


def quality_warnings(
    total_source_rows: int,
    quarantine_rate_pct: float | None,
    duplicate_rate_pct: float | None,
    thresholds: QualityThresholds,
) -> list[str]:
    """Return warning messages; equality with a threshold does not trigger."""
    warnings = []
    if total_source_rows == 0:
        warnings.append("empty_batch")
    if (
        quarantine_rate_pct is not None
        and quarantine_rate_pct > thresholds.quarantine_pct
    ):
        warnings.append("high_quarantine_rate")
    if (
        duplicate_rate_pct is not None
        and duplicate_rate_pct > thresholds.duplicate_pct
    ):
        warnings.append("high_duplicate_rate")
    return warnings


def check_batch_quality(source_file: str, thresholds: QualityThresholds) -> list[str]:
    """Evaluate the committed checkpoint for a newly processed source file."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT q.ingestion_run_id, q.total_source_rows,
                   q.quarantine_rate_pct, q.duplicate_rate_pct
            FROM processed_files AS p
            JOIN vw_ingestion_batch_quality AS q
              ON q.ingestion_run_id = p.ingestion_run_id
            WHERE p.source_file = %s AND q.status = 'success';
            """,
            (source_file,),
        ).fetchone()

    if row is None:
        raise RuntimeError(f"No successful checkpoint metrics for {source_file}")

    run_id, total, quarantine_pct, duplicate_pct = row
    warnings = quality_warnings(
        total,
        float(quarantine_pct) if quarantine_pct is not None else None,
        float(duplicate_pct) if duplicate_pct is not None else None,
        thresholds,
    )
    if not warnings:
        log.info(
            "Batch quality OK | source_file=%s | run_id=%s | total=%s | "
            "quarantine_pct=%s | duplicate_pct=%s",
            source_file, run_id, total, quarantine_pct, duplicate_pct,
        )
    for warning in warnings:
        log.warning(
            "Batch quality warning | rule=%s | source_file=%s | run_id=%s | "
            "total=%s | quarantine_pct=%s | duplicate_pct=%s | "
            "quarantine_limit_pct=%s | duplicate_limit_pct=%s",
            warning, source_file, run_id, total, quarantine_pct, duplicate_pct,
            thresholds.quarantine_pct, thresholds.duplicate_pct,
        )
    return warnings
