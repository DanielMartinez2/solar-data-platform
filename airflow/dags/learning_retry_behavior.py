"""Learning DAG that demonstrates Airflow retry behavior safely."""

from __future__ import annotations

import logging
from datetime import timedelta

from airflow.sdk import dag, get_current_context, task


log = logging.getLogger(__name__)


@dag(
    dag_id="learning_retry_behavior",
    schedule=None,
    catchup=False,
    tags=["learning", "retries", "solar-data-platform"],
)
def learning_retry_behavior():
    """Fail once on purpose, then succeed on the retry."""

    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(minutes=2),
    )
    def fail_once_then_succeed() -> None:
        context = get_current_context()
        task_instance = context["task_instance"]
        try_number = task_instance.try_number

        log.info("Current try number: %s", try_number)

        if try_number == 1:
            raise RuntimeError(
                "Intentional learning failure on the first attempt."
            )

        log.info("Retry succeeded on attempt %s.", try_number)

    fail_once_then_succeed()


learning_retry_behavior()
