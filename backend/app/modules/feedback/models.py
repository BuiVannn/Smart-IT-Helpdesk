"""Model đánh giá sau xử lý."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

RATING_EDIT_WINDOW_HOURS = 24


class TicketRating(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Mỗi ticket ĐÚNG MỘT đánh giá (BR-06) — cưỡng chế bằng UNIQUE constraint."""

    __tablename__ = "ticket_ratings"

    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    rater_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # Bản SAO của assignee lúc đánh giá — denormalization CÓ CHỦ ĐÍCH.
    # Báo cáo điểm hài lòng phải phản ánh người thực sự xử lý lúc đó; nếu ticket
    # được giao lại về sau, báo cáo lịch sử không được đổi theo.
    agent_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (CheckConstraint("score BETWEEN 1 AND 5", name="score"),)

    def is_editable(self, now: datetime | None = None) -> bool:
        """Sửa đánh giá chỉ trong 24 giờ đầu (BR-08)."""
        now = now or datetime.now(UTC)
        return now - self.created_at < timedelta(hours=RATING_EDIT_WINDOW_HOURS)
