"""Model thông báo và khoá chống trùng."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin
from app.modules.notifications.constants import NOTIFICATION_TYPES


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # VARCHAR + CHECK thay vì native ENUM: tập giá trị này sẽ còn được
    # bổ sung, thêm giá trị vào ENUM cần migration (xem ADR-0006).
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(500))
    entity_type: Mapped[str | None] = mapped_column(String(30))
    entity_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in NOTIFICATION_TYPES) + ")", name="type"
        ),
        # Đếm số chưa đọc là truy vấn chạy 30 giây/lần cho MỌI người đang online
        Index(
            "ix_notifications_unread",
            "user_id",
            "created_at",
            postgresql_where="is_read = false",
        ),
    )


class IdempotencyKey(Base):
    """Chống tạo ticket trùng khi client gửi lại request (US-08)."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(SmallInteger)
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
