"""Mixin dùng chung cho model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7


class UUIDPrimaryKeyMixin:
    """Khoá chính UUIDv7 — sinh ở tầng ứng dụng (xem ADR-0011).

    UUIDv7 có tiền tố timestamp nên bản ghi mới luôn chèn vào cuối B-tree,
    không gây phân mảnh index như UUIDv4.
    """

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
