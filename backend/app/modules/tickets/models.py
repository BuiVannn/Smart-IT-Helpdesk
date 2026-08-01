"""Model của module ticket — bảng trung tâm của hệ thống.

Các ràng buộc CHECK ở đây là cưỡng chế các bất biến ở docs/design/03 §5.
Validation ở tầng ứng dụng là trải nghiệm người dùng; CHECK constraint ở
database mới là thứ thật sự bảo vệ dữ liệu.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.tickets.constants import (
    ActorType,
    AiStatus,
    EventType,
    TicketPriority,
    TicketSource,
    TicketStatus,
)


class TicketCategory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ticket_categories"

    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority"),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)


class SlaPolicy(Base, UUIDPrimaryKeyMixin):
    """Chính sách SLA theo mức ưu tiên.

    LƯU Ý: ticket SAO CHÉP hạn SLA vào cột riêng lúc tạo, không tính lại từ
    policy mỗi lần đọc (BR-19). Đổi policy về sau không được làm thay đổi
    hạn của ticket cũ — nếu không, báo cáo lịch sử sẽ sai.
    """

    __tablename__ = "sla_policies"

    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority"), unique=True, nullable=False
    )
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("first_response_minutes > 0 AND resolution_minutes > 0", name="positive"),
        CheckConstraint("resolution_minutes >= first_response_minutes", name="order"),
    )


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tickets"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status"), default=TicketStatus.NEW, nullable=False
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority"),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )

    requester_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    category_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ticket_categories.id", ondelete="SET NULL")
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL")
    )

    source: Mapped[TicketSource] = mapped_column(
        SAEnum(TicketSource, name="ticket_source"), default=TicketSource.WEB, nullable=False
    )
    chat_session_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))

    ai_status: Mapped[AiStatus] = mapped_column(
        SAEnum(AiStatus, name="ai_status"), default=AiStatus.PENDING, nullable=False
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)

    sla_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sla_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Optimistic lock — chống hai Agent cùng nhận một ticket (docs/design/03 §7)
    #
    # ★★ CỘT NÀY CHỈ CÓ TÁC DỤNG NHỜ `__mapper_args__` Ở DƯỚI. ĐỪNG XOÁ.
    #
    # Bản đầu tiên chỉ khai cột rồi so sánh trong Python (`_check_version`) và
    # tự cộng 1 (`_bump`). Đó là đọc-rồi-ghi: hai transaction cùng đọc
    # version=1, cả hai cùng qua bước so sánh, cả hai cùng UPDATE — và câu
    # UPDATE không có `WHERE version = 1` nên người sau ghi đè im lặng lên
    # người trước. Chạy thử hai luồng đồng thời: cả hai đều nhận HTTP 200,
    # database ghi Agent thứ hai, và `version` chỉ lên 2 thay vì 3 (một lần
    # cộng bị mất) nên lần ghi đồng thời kế tiếp cũng lọt.
    #
    # `version_id_col` bảo SQLAlchemy tự thêm `WHERE version = :cũ` vào mọi
    # câu UPDATE và tự tăng giá trị; không khớp thì ném `StaleDataError`.
    # Việc kiểm tra chuyển từ Python xuống đúng chỗ nó phải nằm: database.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)

    requester = relationship("User", foreign_keys=[requester_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    category: Mapped[TicketCategory | None] = relationship()
    comments: Mapped[list["TicketComment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["TicketAttachment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 5 AND 200", name="title_len"),
        CheckConstraint("char_length(description) BETWEEN 10 AND 5000", name="desc_len"),
        CheckConstraint(
            "status IN ('NEW', 'CANCELLED') OR assignee_id IS NOT NULL", name="assignee"
        ),
        CheckConstraint(
            "status NOT IN ('RESOLVED', 'CLOSED') OR "
            "(resolved_at IS NOT NULL AND char_length(coalesce(resolution_note, '')) >= 10)",
            name="resolved",
        ),
        CheckConstraint("paused_seconds >= 0", name="paused"),
        # Index đầy đủ (gồm partial index) xem docs/design/04 §5.1.
        # Ở đây chỉ khai báo các index cơ bản; phần còn lại thêm ở migration.
        Index("ix_tickets_requester_created", "requester_id", "created_at"),
        Index("ix_tickets_assignee_status", "assignee_id", "status"),
        Index("ix_tickets_search", "search_vector", postgresql_using="gin"),
    )

    # SQLAlchemy tự tăng `version` và tự thêm điều kiện vào WHERE — xem chú
    # thích dài ở khai báo cột. KHÔNG đặt `version_id_generator=False`: để
    # SQLAlchemy tự sinh thì không chỗ nào trong service cộng tay được nữa,
    # và đó chính là điều ta muốn.
    __mapper_args__ = {"version_id_col": version}

    @property
    def is_open(self) -> bool:
        from app.modules.tickets.constants import OPEN_STATUSES

        return self.status in OPEN_STATUSES

    def __repr__(self) -> str:
        return f"<Ticket {self.code} [{self.status}]>"


class TicketComment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped[Ticket] = relationship(back_populates="comments")
    author = relationship("User")

    __table_args__ = (CheckConstraint("char_length(body) BETWEEN 1 AND 5000", name="body_len"),)

    def is_visible_to(self, user) -> bool:
        """Bình luận nội bộ chỉ IT Agent và Admin thấy (BR-10)."""
        if not self.is_internal:
            return True
        return user.role in ("IT_AGENT", "ADMIN")


class TicketAttachment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ticket_attachments"

    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ticket_comments.id", ondelete="CASCADE")
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Tên lưu trong object storage là UUID, KHÔNG dùng tên gốc → chống path traversal
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_by: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped[Ticket] = relationship(back_populates="attachments")

    __table_args__ = (CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="size"),)


class TicketEvent(Base, UUIDPrimaryKeyMixin):
    """Nhật ký thay đổi — bảng CHỈ GHI THÊM (BR-17).

    Không có API sửa/xoá. Đây là nguồn sự thật cho lịch sử ticket và cho
    việc truy vết khi có tranh cãi.
    """

    __tablename__ = "ticket_events"

    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_type: Mapped[ActorType] = mapped_column(
        SAEnum(ActorType, name="actor_type"), default=ActorType.USER, nullable=False
    )
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="event_type"), nullable=False
    )
    field_name: Mapped[str | None] = mapped_column(String(50))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped[Ticket] = relationship(back_populates="events")
    # actor có thể NULL: sự kiện do hệ thống hoặc AI sinh ra thì không có người
    actor = relationship("User")


class AiClassification(Base, UUIDPrimaryKeyMixin):
    """Lưu MỌI lần AI phân loại, kể cả thất bại.

    Đây là nguồn dữ liệu duy nhất cho báo cáo độ chính xác AI (US-22) và
    cho việc cải thiện prompt.
    """

    __tablename__ = "ai_classifications"

    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    suggested_category_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ticket_categories.id", ondelete="SET NULL")
    )
    suggested_priority: Mapped[TicketPriority | None] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority")
    )
    confidence: Mapped[float | None] = mapped_column()
    reasoning: Mapped[str | None] = mapped_column(Text)
    was_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    was_accepted: Mapped[bool | None] = mapped_column(Boolean)
    corrected_category_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ticket_categories.id", ondelete="SET NULL")
    )
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # `foreign_keys` là BẮT BUỘC: bảng này có hai khoá ngoại trỏ cùng tới
    # ticket_categories (loại AI gợi ý và loại người sửa lại), nên SQLAlchemy
    # không tự đoán được quan hệ nào đi theo cột nào.
    suggested_category: Mapped[TicketCategory | None] = relationship(
        foreign_keys=[suggested_category_id]
    )
