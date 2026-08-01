"""Celery task của module ticket.

Task chỉ là VỎ MỎNG gọi service — toàn bộ logic nằm ở `classifier.py` và
`service.py`. Nhờ vậy cùng một logic chạy được trong worker, trong test và
trong script đánh giá, mà không cần dựng Celery.

Các task này chạy ở hàng đợi `ai` riêng (xem `celery_app.task_routes`): LLM
chậm không được làm nghẽn hàng đợi gửi thông báo.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger

# Nạp TOÀN BỘ model để SQLAlchemy phân giải được mọi quan hệ khoá ngoại.
# Thiếu dòng này, worker chỉ import vài model sẽ chết ở lần chạy đầu tiên với
# lỗi "could not find table" — và chỉ chết trong worker, không chết trong test.
from app.db import all_models  # noqa: F401
from app.db.session import session_scope
from app.modules.tickets.classifier import build_classifier
from app.modules.tickets.constants import AiStatus
from app.modules.tickets.models import Ticket
from app.modules.tickets.service import TicketService

logger = get_logger(__name__)

RECONCILE_BATCH_SIZE = 50


@celery_app.task(
    bind=True,
    name="app.modules.tickets.tasks.classify_ticket",
    max_retries=3,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
)
def classify_ticket(self, ticket_id: str) -> dict:
    """Phân loại một ticket (US-19). Được xếp hàng ngay sau khi tạo ticket.

    Chạy lại nhiều lần là an toàn: `TicketClassifier` bỏ qua ticket đã có
    `ai_status` khác PENDING. Điều này quan trọng vì `task_acks_late=True`
    nghĩa là worker chết giữa chừng thì task được giao lại cho worker khác.
    """
    with session_scope() as db:
        outcome = asyncio.run(build_classifier(db).classify(UUID(ticket_id)))

    return {
        "ticket_id": str(outcome.ticket_id),
        "ai_status": str(outcome.ai_status),
        "category": outcome.suggestion.category_slug if outcome.suggestion else None,
        "confidence": outcome.suggestion.confidence if outcome.suggestion else None,
        "source": str(outcome.suggestion.source) if outcome.suggestion else None,
        "latency_ms": outcome.latency_ms,
        "error": outcome.error,
    }


@celery_app.task(name="app.modules.tickets.tasks.reconcile_pending")
def reconcile_pending() -> dict:
    """Nhặt lại các ticket kẹt ở PENDING (chạy mỗi 10 phút).

    Đây là lưới an toàn cho việc KHÔNG dùng transactional outbox (ADR-0007):
    nếu Redis chết đúng lúc `POST /tickets` gọi `.delay()`, việc phân loại rơi
    mất mà không ai biết. Không có job này, ticket sẽ nằm ở "Đang phân loại…"
    vĩnh viễn — trạng thái tệ hơn cả FAILED, vì FAILED ít nhất còn hiện trong
    hàng chờ thủ công.

    Xếp hàng lại thay vì phân loại ngay tại chỗ: 50 lời gọi LLM tuần tự sẽ
    vượt `task_time_limit` 300 giây và bị giết giữa chừng.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.AI_CLASSIFY_STALE_MINUTES)

    with session_scope() as db:
        stale = list(
            db.execute(
                select(Ticket.id)
                .where(Ticket.ai_status == AiStatus.PENDING, Ticket.created_at <= cutoff)
                .order_by(Ticket.created_at)
                .limit(RECONCILE_BATCH_SIZE)
            )
            .scalars()
            .all()
        )

    for ticket_id in stale:
        classify_ticket.delay(str(ticket_id))

    if stale:
        logger.warning(
            f"đối soát: phát hiện {len(stale)} ticket kẹt ở PENDING, đã xếp hàng lại",
            extra={"extra_fields": {"count": len(stale)}},
        )
    return {"requeued": len(stale), "batch_limit": RECONCILE_BATCH_SIZE}


@celery_app.task(name="app.modules.tickets.tasks.auto_close_resolved")
def auto_close_resolved() -> dict:
    """Đóng ticket RESOLVED quá 3 ngày không phản hồi (US-14, chạy 01:00 hằng ngày).

    Cũng là lúc chốt sổ độ chính xác của AI: ticket đóng mà không ai sửa
    phân loại nghĩa là gợi ý của AI được chấp nhận (US-21).
    """
    with session_scope() as db:
        closed = TicketService(db).auto_close_resolved()

    if closed:
        logger.info(f"tự động đóng {len(closed)} ticket đã xử lý xong quá hạn phản hồi")
    return {"closed": len(closed), "ticket_ids": [str(t) for t in closed]}
