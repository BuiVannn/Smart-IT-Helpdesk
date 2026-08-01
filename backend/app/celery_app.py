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
    # Giới hạn thời gian chờ broker. WORKER cố tình KHÔNG giới hạn số lần thử
    # lại ở đây: worker phải tự kết nối lại vô hạn sau khi Redis restart.
    # Đường ĐẨY VIỆC dùng kết nối riêng, xem `publish_connection()` bên dưới.
    broker_transport_options={"socket_connect_timeout": 2, "socket_timeout": 2},
    broker_connection_retry_on_startup=False,
    # ★ KHÔNG thử lại khi đẩy việc — đặt toàn cục vì tám thành viên khác sẽ
    # viết `.delay()` theo phản xạ và không ai nhớ truyền `retry=False`.
    task_publish_retry=False,
    # ★ KHÔNG lưu kết quả tác vụ. Đây là bản vá cho một sự cố đo được, không
    # phải tối ưu suy đoán: backend Redis mở một pub/sub "ResultConsumer" ngay
    # trong `apply_async`, và khi backend không kết nối được thì riêng bước đó
    # ngốn **19,2 giây** trước khi chịu báo lỗi — trong khi broker vẫn sống
    # nguyên. Không chỗ nào trong dự án đọc kết quả tác vụ (không ai gọi
    # `.get()`), nên bỏ hẳn kết quả vừa gỡ được điểm treo vừa đỡ tốn Redis.
    # Kết quả tác vụ vẫn xuất hiện đầy đủ trong log của worker.
    task_ignore_result=True,
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


def publish_connection():
    """Kết nối CHỈ dùng để đẩy việc từ trong một request HTTP — thất bại ngay.

    ★ VÌ SAO PHẢI TÁCH RIÊNG, ĐỪNG GỘP VÀO `broker_transport_options`:
    kombu tự thử lại việc mở kết nối theo lịch nghỉ 0s → 2s → 4s. Đo thực tế
    khi Redis chết, một cú `POST /tickets` mất **6,1 giây** chỉ để chờ ba lần
    thử đó — và con số này KHÔNG đổi theo `socket_connect_timeout`, nên rất
    dễ chỉnh sai chỗ. `max_retries=0` gỡ được, xuống còn 0,09 giây.

    Nhưng đặt `max_retries=0` vào cấu hình toàn cục thì WORKER dùng chung, và
    worker sẽ CHẾT HẲN ngay lần đầu Redis chớp tắt thay vì kết nối lại — đã
    kiểm chứng bằng `docker restart redis`: worker thoát với
    `kombu.exceptions.OperationalError`. Hai bên cần hai chính sách ngược
    nhau: người đẩy việc bỏ cuộc ngay, worker kiên trì mãi.

    Việc bị rơi sẽ được job đối soát nhặt lại trong 10 phút (ADR-0007).

    Dùng:
        with publish_connection() as conn:
            my_task.apply_async(args=[...], retry=False, connection=conn)
    """
    return celery_app.connection_for_write(
        transport_options={
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
            "max_retries": 0,
        }
    )
