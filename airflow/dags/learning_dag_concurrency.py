"""Manual concurrency drill demonstrating max_active_runs=1.

Trigger two DAG runs close together. Only the first can be running while
the second waits, even if the Airflow executor has spare worker capacity.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task
from resilience_drill_helpers import hold_for_seconds


log = logging.getLogger(__name__)


@dag(
    dag_id="learning_dag_concurrency",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 29, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=4),
    tags=["learning", "resilience", "concurrency"],
)
def learning_dag_concurrency():
    @task(
        execution_timeout=timedelta(seconds=120),
        retries=0,
    )
    def bounded_sleep() -> None:
        context = get_current_context()
        conf = context["dag_run"].conf or {}
        seconds = conf.get("hold_seconds", 45)
        if type(seconds) is not int or not 1 <= seconds <= 90:
            raise ValueError("hold_seconds must be an integer between 1 and 90")
        log.info(
            "Concurrency drill | max_active_runs=1 | hold_seconds=%s",
            seconds,
        )
        hold_for_seconds(
            seconds, scenario="concurrency", run_id=context["run_id"],
        )

    bounded_sleep()


learning_dag_concurrency()
