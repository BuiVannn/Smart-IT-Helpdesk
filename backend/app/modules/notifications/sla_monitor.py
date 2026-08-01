"""Quét SLA và sinh cảnh báo (US-35) — LỚP NGHIỆP VỤ, không phụ thuộc Celery.

★ Tách khỏi `tasks.py` để test được. Một job chỉ tồn tại bên trong Celery
task là một job chỉ chạy được khi có Redis, có worker, có beat — nghĩa là
trong thực tế nó không bao giờ được test, và nó sẽ hỏng đúng lúc không ai
nhìn. Task ở `tasks.py` giờ chỉ mở session rồi gọi lớp này.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.notifications.service import (
    ENTITY_TICKET,
    NotificationService,
    sla_at_risk_message,
    sla_breached_message,
)
from app.modules.tickets.constants import OPEN_STATUSES, ActorType, EventType, SlaState
from app.modules.tickets.models import Ticket, TicketEvent
from app.modules.tickets.sla import BusinessCalendar, SlaCalculator
from app.modules.users.constants import UserRole
from app.modules.users.models import Holiday, User

logger = get_logger(__name__)


@dataclass
class SlaScanResult:
    scanned: int = 0
    at_risk: int = 0
    breached: int = 0


class SlaMonitor:
    """Nhắc trước hạn và báo đã trễ hạn.

    **Idempotent theo TRẠNG THÁI, không theo khoảng thời gian.** Job không hỏi
    "có gì thay đổi từ lần chạy trước", nó hỏi "ticket nào đang quá hạn mà
    chưa được báo". Nhờ vậy AC cuối của US-35 tự thoả: hệ thống tắt ba ngày,
    bật lại vẫn phát hiện đúng những ticket đã trễ trong ba ngày đó — không
    cần lưu lại mốc chạy lần trước, không sợ mốc đó bị mất.

    Hai cột `sla_warned_at` / `sla_breached_at` là dấu "đã báo rồi": chạy lại
    bao nhiêu lần cũng không sinh thông báo trùng.
    """

    def __init__(self, session: Session) -> None:
        self.db = session
        self.notifier = NotificationService(session)

    def run(self, now: datetime | None = None) -> SlaScanResult:
        now = now or datetime.now(UTC)
        result = SlaScanResult()

        sla = SlaCalculator(self._calendar())
        admin_ids = self._active_admin_ids()
        candidates = self._candidates()
        result.scanned = len(candidates)

        for ticket in candidates:
            state = sla.state(
                created_at=ticket.created_at,
                due_at=ticket.sla_resolution_due_at,
                resolved_at=ticket.resolved_at,
                now=now,
                paused_seconds=ticket.paused_seconds,
            )

            if state is SlaState.BREACHED and ticket.sla_breached_at is None:
                title, body = sla_breached_message(
                    ticket.code, ticket.title, ticket.sla_resolution_due_at
                )
                # Quá hạn thì báo cho CẢ Admin, không chỉ assignee: assignee
                # nghỉ phép chính là lý do phổ biến nhất khiến ticket trễ hạn,
                # nên báo mỗi assignee là báo đúng người không xử lý được.
                self.notifier.notify_many(
                    [ticket.assignee_id, *admin_ids],
                    notification_type="SLA_BREACHED",
                    title=title,
                    body=body,
                    entity_type=ENTITY_TICKET,
                    entity_id=ticket.id,
                    moment=now,
                )
                ticket.sla_breached_at = now
                self._record(ticket, EventType.SLA_BREACHED)
                result.breached += 1

            elif state is SlaState.AT_RISK and ticket.sla_warned_at is None:
                title, body = sla_at_risk_message(
                    ticket.code, ticket.title, ticket.sla_resolution_due_at
                )
                self.notifier.notify(
                    user_id=ticket.assignee_id,
                    notification_type="SLA_AT_RISK",
                    title=title,
                    body=body,
                    entity_type=ENTITY_TICKET,
                    entity_id=ticket.id,
                    moment=now,
                )
                ticket.sla_warned_at = now
                self._record(ticket, EventType.SLA_WARNED)
                result.at_risk += 1

        self.db.flush()
        if result.at_risk or result.breached:
            logger.info(
                "quét SLA xong",
                extra={"extra_fields": {"at_risk": result.at_risk, "breached": result.breached}},
            )
        return result

    # ── Truy vấn ──────────────────────────────────────────────────────

    def _candidates(self) -> list[Ticket]:
        """Chỉ nạp ticket CÓ THỂ cần báo.

        Điều kiện cuối — còn thiếu ít nhất một trong hai dấu đã-báo — là thứ
        giữ cho job này rẻ khi dữ liệu lớn dần: ticket đã báo đủ cả hai không
        bao giờ được đọc lên lại.
        """
        return list(
            self.db.execute(
                select(Ticket)
                .where(
                    Ticket.status.in_(OPEN_STATUSES),
                    Ticket.sla_resolution_due_at.is_not(None),
                    (Ticket.sla_warned_at.is_(None)) | (Ticket.sla_breached_at.is_(None)),
                )
                .order_by(Ticket.sla_resolution_due_at)
                .limit(settings.SLA_MONITOR_BATCH_SIZE)
            )
            .scalars()
            .all()
        )

    def _active_admin_ids(self) -> list:
        return list(
            self.db.execute(
                select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
            )
            .scalars()
            .all()
        )

    def _calendar(self) -> BusinessCalendar:
        return BusinessCalendar(
            start_hour=settings.BUSINESS_HOUR_START,
            end_hour=settings.BUSINESS_HOUR_END,
            holidays=frozenset(
                row.holiday_date.date() for row in self.db.execute(select(Holiday)).scalars().all()
            ),
        )

    def _record(self, ticket: Ticket, event_type: EventType) -> None:
        """Ghi vào nhật ký ticket với actor SYSTEM.

        Thông báo có thể bị người dùng đánh dấu đã đọc rồi quên; nhật ký thì
        không. Khi cần trả lời "vì sao ticket này trễ mà không ai biết",
        nguồn sự thật phải là `ticket_events` (BR-17).
        """
        self.db.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=None,
                actor_type=ActorType.SYSTEM,
                event_type=event_type,
                field_name="sla_resolution_due_at",
                new_value=(
                    ticket.sla_resolution_due_at.isoformat()
                    if ticket.sla_resolution_due_at
                    else None
                ),
                event_metadata={
                    "assigneeId": str(ticket.assignee_id) if ticket.assignee_id else None
                },
            )
        )
