"""Model chatbot: ChatSession, ChatMessage, ChatCitation, ChatFeedback."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin
from app.modules.chatbot.constants import MessageRole


class ChatSession(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "chat_sessions"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Chỉ số tự phục vụ (mục tiêu G3): phiên chat KHÔNG dẫn tới ticket = thành công
    led_to_ticket: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "chat_messages"

    session_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # true = không tìm thấy tài liệu liên quan ⇒ chatbot đã TỪ CHỐI trả lời.
    # Đây là dữ liệu cho US-27 (tìm khoảng trống của kho tài liệu).
    no_context_found: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    citations: Mapped[list["ChatCitation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class ChatCitation(Base, UUIDPrimaryKeyMixin):
    """Trích dẫn — chứng minh câu trả lời dựa trên tài liệu nội bộ nào.

    article_id được giữ lại KỂ CẢ khi chunk bị xoá (chunk_id SET NULL),
    nhờ vậy lịch sử hội thoại vẫn trỏ đúng bài viết sau mỗi lần re-index.
    """

    __tablename__ = "chat_citations"

    message_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("article_chunks.id", ondelete="SET NULL")
    )
    article_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    message: Mapped[ChatMessage] = relationship(back_populates="citations")
    # Nạp sẵn bài viết để hiển thị tiêu đề + đường dẫn trong lịch sử hội thoại.
    # Chỉ là quan hệ ORM, không thêm cột nào nên không cần migration.
    article = relationship("KbArticle", lazy="joined")


class ChatFeedback(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "chat_feedback"

    message_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
