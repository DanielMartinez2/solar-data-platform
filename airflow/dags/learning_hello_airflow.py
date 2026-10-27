"""First learning DAG for the Solar Data Platform.

This DAG is intentionally independent from the real solar pipeline. Its goal
is to make the Airflow lifecycle visible before we orchestrate migrations,
ingestion, and dbt.
"""

from __future__ import annotations

import logging

from airflow.sdk import dag, task


log = logging.getLogger(__name__)


@dag(
    dag_id="learning_hello_airflow",
    schedule=None,
    catchup=False,
    tags=["learning", "solar-data-platform"],
)
def learning_hello_airflow():
    """Demonstrate DAG discovery, dependencies, execution, and task logs."""

    @task
    def start() -> None:
        log.info("Learning DAG started.")

    @task
    def hello_airflow() -> None:
        log.info(
            "Hello from Airflow. This task was scheduled and executed "
            "through the LocalExecutor."
        )

    @task
    def finish() -> None:
        log.info("Learning DAG finished successfully.")

    start_task = start()
    hello_task = hello_airflow()
    finish_task = finish()

    start_task >> hello_task >> finish_task


learning_hello_airflow()
