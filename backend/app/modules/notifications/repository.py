"""Truy vấn thông báo. Không chứa logic nghiệp vụ, không commit."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.modules.notifications.models import Notification


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, notification: Notification) -> Notification:
        self.session.add(notification)
        self.session.flush()
        return notification

    def list_for_user(
        self, user_id: UUID, params: PageParams, *, unread_only: bool = False
    ) -> tuple[list[Notification], int]:
        stmt: Select = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        # ★ Tie-breaker `id.desc()` là BẮT BUỘC: `created_at` do
        # `transaction_timestamp()` sinh ra, nên nhiều thông báo ghi trong CÙNG
        # một transaction (giao việc + đổi trạng thái) có mốc giống hệt nhau.
        # Thiếu nó, hai trang liên tiếp có thể trả trùng hoặc bỏ sót bản ghi.
        rows = (
            self.session.execute(
                stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset(params.offset)
                .limit(params.limit)
            )
            .scalars()
            .all()
        )
        return list(rows), total

    def count_unread(self, user_id: UUID) -> int:
        """Truy vấn nóng nhất của hệ thống — chạy 30 giây/lần cho mỗi người online.

        Có partial index `ix_notifications_unread` phục vụ đúng câu này.
        """
        return self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        ).scalar_one()

    def exists_recent(
        self,
        user_id: UUID,
        notification_type: str,
        entity_id: UUID | None,
        since: datetime,
    ) -> bool:
        """Đã có thông báo cùng loại, cùng đối tượng, trong cửa sổ chống lặp chưa."""
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.type == notification_type,
                Notification.created_at >= since,
            )
        )
        # `entity_id IS NULL` không so sánh được bằng `=` — phải tách nhánh.
        stmt = stmt.where(
            Notification.entity_id.is_(None)
            if entity_id is None
            else Notification.entity_id == entity_id
        )
        return self.session.execute(stmt).scalar_one() > 0

    def mark_read(self, user_id: UUID, notification_id: UUID, moment: datetime) -> int:
        """Đánh dấu một thông báo đã đọc.

        `user_id` nằm trong WHERE chứ không kiểm tra ở tầng trên: người dùng
        không được đánh dấu hộ thông báo của người khác, và điều kiện đó phải
        nằm trong chính câu UPDATE để không ai đi vòng qua được.
        """
        result = self.session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=moment)
        )
        return result.rowcount or 0

    def mark_all_read(self, user_id: UUID, moment: datetime) -> int:
        result = self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True, read_at=moment)
        )
        return result.rowcount or 0

    def get_owned(self, user_id: UUID, notification_id: UUID) -> Notification | None:
        return self.session.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        ).scalar_one_or_none()
