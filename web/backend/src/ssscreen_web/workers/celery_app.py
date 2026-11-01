from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from celery import Celery
from kombu import Exchange, Queue
from sqlalchemy import select

from ssscreen_web.application.pipelines import queue_for_topic
from ssscreen_web.domain.enums import AttemptStatus, OutboxStatus, TaskStatus
from ssscreen_web.infrastructure.database import get_session_factory
from ssscreen_web.infrastructure.models import Attempt, Event, OutboxMessage, Run, Task
from ssscreen_web.settings import get_settings

settings = get_settings()
celery_app = Celery("ssscreen_web", broker=settings.redis_url)
celery_app.conf.update(
    task_default_queue="control",
    task_default_exchange="control",
    task_default_routing_key="control",
    task_queues=(
        Queue("control", Exchange("control", type="direct"), routing_key="control"),
        Queue("cpu", Exchange("cpu", type="direct"), routing_key="cpu"),
    ),
    task_routes={
        "ssscreen_web.example.generate_json": {"queue": "control"},
        "ssscreen_web.dataset.mp_offline": {"queue": "cpu"},
        "ssscreen_web.dataset.wbm_upload": {"queue": "cpu"},
        "ssscreen_web.composition.screen": {"queue": "cpu"},
        "ssscreen_web.condensation.batch": {"queue": "cpu"},
    },
    imports=(
        "ssscreen_web.workers.example_task",
        "ssscreen_web.workers.mp_dataset_task",
        "ssscreen_web.workers.wbm_dataset_task",
        "ssscreen_web.workers.composition_task",
        "ssscreen_web.workers.condensation_task",
    ),
    task_always_eager=settings.celery_task_always_eager,
    task_store_eager_result=False,
    broker_connection_retry_on_startup=True,
)


def dispatch_pending_outbox() -> int:
    published = 0
    with get_session_factory()() as session:
        messages = list(
            session.scalars(
                select(OutboxMessage)
                .where(OutboxMessage.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]))
                .order_by(OutboxMessage.created_at)
                .with_for_update(skip_locked=True)
            ).all()
        )
        for message in messages:
            try:
                celery_app.send_task(
                    message.topic,
                    kwargs=message.payload,
                    queue=queue_for_topic(message.topic),
                )
                message.status = OutboxStatus.PUBLISHED
                message.published_at = datetime.now(UTC)
                message.last_error = None
                message.publish_attempts += 1
                published += 1
            except Exception as error:  # broker failures remain visible and reconcilable
                message.status = OutboxStatus.FAILED
                message.publish_attempts += 1
                message.last_error = type(error).__name__
        session.commit()
    return published


def reconcile_stale_published_outbox() -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().outbox_redelivery_seconds)
    reconciled = 0
    with get_session_factory()() as session:
        messages = list(
            session.scalars(
                select(OutboxMessage)
                .where(
                    OutboxMessage.status == OutboxStatus.PUBLISHED,
                    OutboxMessage.published_at < cutoff,
                )
                .order_by(OutboxMessage.published_at)
                .with_for_update(skip_locked=True)
            ).all()
        )
        for message in messages:
            task_id = message.payload.get("task_id")
            attempt_number = message.payload.get("attempt_number")
            if not isinstance(task_id, str) or not isinstance(attempt_number, int):
                continue
            try:
                parsed_task_id = uuid.UUID(task_id)
            except ValueError:
                continue
            task = session.get(Task, parsed_task_id)
            attempt = session.scalar(
                select(Attempt).where(
                    Attempt.task_id == parsed_task_id, Attempt.number == attempt_number
                )
            )
            if (
                task is None
                or attempt is None
                or task.status != TaskStatus.QUEUED
                or attempt.status != AttemptStatus.QUEUED
            ):
                continue
            run = session.get(Run, task.run_id)
            message.status = OutboxStatus.PENDING
            message.published_at = None
            message.last_error = "delivery.unconfirmed"
            session.add(
                Event(
                    project_id=run.project_id,
                    run_id=run.id,
                    task_id=task.id,
                    kind="task.delivery_reconciled",
                    payload={"attempt": attempt.number},
                )
            )
            reconciled += 1
        session.commit()
    return reconciled
