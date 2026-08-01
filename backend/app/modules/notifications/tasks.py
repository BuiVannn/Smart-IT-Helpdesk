"""Job định kỳ của module thông báo (US-35 — nhắc trước hạn SLA).

★ `celery_app.beat_schedule` đã trỏ tới `monitor_sla` từ trước khi file này
tồn tại, nên worker ném `NotRegistered` mỗi 5 phút. File này khép lại cái
vòng đó.

Task chỉ là VỎ MỎNG mở session rồi gọi `SlaMonitor` — toàn bộ logic nằm ở
`sla_monitor.py` để test được mà không cần dựng Redis, worker và beat.

Chạy ở hàng đợi `notifications` riêng (xem `celery_app.task_routes`): job này
phải chạy đúng giờ, không được xếp sau một lời gọi LLM 20 giây.
"""

from __future__ import annotations

from app.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger

# Nạp toàn bộ model trước khi dựng mapper — thiếu dòng này worker chết ở lần
# chạy đầu tiên với "could not find table", và chỉ chết trong worker.
from app.db import all_models  # noqa: F401
from app.db.session import session_scope
from app.modules.notifications.sla_monitor import SlaMonitor

logger = get_logger(__name__)


@celery_app.task(name="app.modules.notifications.tasks.monitor_sla")
def monitor_sla() -> dict:
    """Quét ticket đang mở, nhắc sắp trễ hạn và báo đã trễ hạn (mỗi 5 phút)."""
    with session_scope() as db:
        result = SlaMonitor(db).run()

    return {
        "scanned": result.scanned,
        "at_risk": result.at_risk,
        "breached": result.breached,
        "batch_limit": settings.SLA_MONITOR_BATCH_SIZE,
    }
