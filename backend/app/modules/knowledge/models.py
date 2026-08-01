"""Model kho tri thức: KbCategory, KbArticle, ArticleChunk."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.knowledge.constants import ArticleStatus


class KbCategory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kb_categories"

    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("kb_categories.id", ondelete="RESTRICT")
    )
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)


class KbArticle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "kb_articles"

    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ArticleStatus] = mapped_column(
        SAEnum(ArticleStatus, name="article_status"),
        default=ArticleStatus.DRAFT,
        nullable=False,
    )
    kb_category_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("kb_categories.id", ondelete="RESTRICT")
    )
    ticket_category_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ticket_categories.id", ondelete="SET NULL")
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    author_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # NULL hoặc < updated_at  ⇒  cần index lại
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)

    chunks: Mapped[list["ArticleChunk"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    # Quan hệ ORM thuần, không thêm cột nên không cần migration.
    category: Mapped[KbCategory | None] = relationship(foreign_keys=[kb_category_id])
    author = relationship("User")

    __table_args__ = (
        CheckConstraint("status <> 'PUBLISHED' OR published_at IS NOT NULL", name="published"),
        CheckConstraint("char_length(content_md) >= 20", name="content_len"),
        Index("ix_articles_search", "search_vector", postgresql_using="gin"),
    )

    @property
    def is_indexable(self) -> bool:
        """Chỉ bài PUBLISHED mới được đưa vào chỉ mục RAG (BR-11)."""
        return self.status == ArticleStatus.PUBLISHED


class ArticleChunk(Base, UUIDPrimaryKeyMixin):
    """Đoạn văn bản kèm embedding — đơn vị truy xuất của RAG.

    Đây là DỮ LIỆU DẪN XUẤT, luôn tái tạo được từ kb_articles bằng lệnh
    `python scripts/reindex_kb.py --all`. Không bao giờ là nguồn sự thật.
    """

    __tablename__ = "article_chunks"

    article_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSIONS), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    article: Mapped[KbArticle] = relationship(back_populates="chunks")

    __table_args__ = (UniqueConstraint("article_id", "chunk_index", name="chunk"),)
