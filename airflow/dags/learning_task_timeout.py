"""Manual timeout drill; no database access and no subprocesses."""

from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task
from resilience_drill_helpers import hold_for_seconds


log = logging.getLogger(__name__)


@dag(
    dag_id="learning_task_timeout",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 29, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=2),
    tags=["learning", "resilience", "timeout"],
)
def learning_task_timeout():
    @task(
        execution_timeout=timedelta(seconds=5),
        retries=0,
    )
    def bounded_sleep() -> None:
        context = get_current_context()
        conf = context["dag_run"].conf or {}
        seconds = conf.get("hold_seconds", 15)
        if type(seconds) is not int or not 1 <= seconds <= 30:
            raise ValueError("hold_seconds must be an integer between 1 and 30")
        log.info(
            "Timeout drill | configured_seconds=%s | execution_timeout_seconds=5",
            seconds,
        )
        hold_for_seconds(
            seconds, scenario="timeout", run_id=context["run_id"],
        )

    bounded_sleep()


learning_task_timeout()
