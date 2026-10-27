from dataclasses import replace

import pytest

from scripts.benchmark_ingestion import (
    BenchmarkResult,
    summarize_timings,
    validate_consistent_results,
)


def build_result() -> BenchmarkResult:
    return BenchmarkResult(
        strategy="copy-staging",
        classification_seconds=3.0,
        accepted_insert_seconds=7.0,
        quarantine_insert_seconds=1.0,
        audit_finalize_seconds=0.01,
        total_seconds=11.0,
        accepted_count=283_392,
        inserted_readings_count=283_392,
        quarantined_count=2_016,
        inserted_quarantined_count=2_016,
        duplicate_count=1_440,
    )


def test_summarize_timings_calculates_expected_statistics():
    stats = summarize_timings(
        [10.0, 2.0, 8.0, 4.0, 6.0]
    )

    assert stats.minimum == 2.0
    assert stats.maximum == 10.0
    assert stats.average == 6.0
    assert stats.median == 6.0


def test_summarize_timings_supports_even_number_of_runs():
    stats = summarize_timings(
        [1.0, 3.0, 9.0, 11.0]
    )

    assert stats.median == 6.0


def test_summarize_timings_rejects_empty_input():
    with pytest.raises(
        ValueError,
        match="At least one timing value",
    ):
        summarize_timings([])


def test_validate_consistent_results_accepts_same_counts():
    first = build_result()
    second = replace(
        first,
        classification_seconds=5.0,
        accepted_insert_seconds=12.0,
        total_seconds=20.0,
    )

    validate_consistent_results(
        [first, second]
    )


def test_validate_consistent_results_rejects_count_changes():
    first = build_result()
    second = replace(
        first,
        inserted_readings_count=283_391,
    )

    with pytest.raises(
        RuntimeError,
        match="inconsistent row counts",
    ):
        validate_consistent_results(
            [first, second]
        )


def test_validate_consistent_results_rejects_empty_input():
    with pytest.raises(
        ValueError,
        match="At least one benchmark result",
    ):
        validate_consistent_results([])
