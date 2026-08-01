"""Schema của module thông báo (F6 — US-33 → US-36)."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel, StrictModel


class NotificationResponse(ResponseModel):
    """Một thông báo.

    `entityType` + `entityId` là thứ frontend dùng để điều hướng. Cố tình
    KHÔNG trả đường dẫn dựng sẵn: backend không nên biết cấu trúc URL của
    frontend, và khi frontend đổi route thì thông báo cũ trong DB sẽ trỏ sai.
    """

    id: UUID
    type: str
    title: str
    body: str | None = None
    entity_type: str | None = Field(default=None, serialization_alias="entityType")
    entity_id: UUID | None = Field(default=None, serialization_alias="entityId")
    is_read: bool = Field(serialization_alias="isRead")
    read_at: datetime | None = Field(default=None, serialization_alias="readAt")
    created_at: datetime = Field(serialization_alias="createdAt")


class UnreadCountResponse(ResponseModel):
    """Kết quả của endpoint được gọi 30 giây một lần cho MỌI người đang online.

    Chỉ có đúng một con số — mọi thứ thêm vào đây đều nhân với số người dùng
    và với tần suất polling (ADR-0008).
    """

    count: int


class MarkReadResponse(ResponseModel):
    updated: int


class MarkAllReadRequest(StrictModel):
    """Rỗng có chủ ý — để sau này thêm được bộ lọc (chỉ đánh dấu theo loại)
    mà không phải đổi chữ ký endpoint."""
