"""Celery application factory."""

from celery import Celery

from config import settings

celery_app = Celery(
    "pg_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.tasks.call_retry",
        "workers.tasks.whatsapp_send",
        "workers.tasks.reminders",
        "workers.tasks.post_call",
        "workers.tasks.reengagement",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
