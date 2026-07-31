"""Khởi tạo Celery.

Hàng đợi RIÊNG cho AI và cho thông báo (mẫu bulkhead) — AI chậm không được
làm nghẽn việc gửi thông báo.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "smart_it_helpdesk",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "app.modules.tickets.tasks.*": {"queue": "ai"},
        "app.modules.knowledge.tasks.*": {"queue": "ai"},
        "app.modules.notifications.tasks.*": {"queue": "notifications"},
    },
    # Job định kỳ — xem docs/design/08 §7.3 về cảnh báo khi job NGỪNG chạy
    beat_schedule={
        "sla-monitor": {
            "task": "app.modules.notifications.tasks.monitor_sla",
            "schedule": crontab(minute="*/5"),
        },
        "auto-close-resolved": {
            "task": "app.modules.tickets.tasks.auto_close_resolved",
            "schedule": crontab(hour="1", minute="0"),
        },
        "reconcile-pending-classification": {
            "task": "app.modules.tickets.tasks.reconcile_pending",
            "schedule": crontab(minute="*/10"),
        },
        "reconcile-stale-index": {
            "task": "app.modules.knowledge.tasks.reconcile_stale_index",
            "schedule": crontab(minute="0"),
        },
        "cleanup-expired-tokens": {
            "task": "app.modules.auth.tasks.cleanup_expired_tokens",
            "schedule": crontab(hour="2", minute="30"),
        },
    },
)

# Các module sẽ được thêm vào đây khi có tasks.py:
celery_app.autodiscover_tasks(
    ["app.modules.tickets", "app.modules.knowledge", "app.modules.notifications",
     "app.modules.auth"],
    related_name="tasks",
)
