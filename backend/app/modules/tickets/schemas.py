"""Schema của module ticket (US-08 → US-18).

Giới hạn độ dài ở đây PHẢI khớp với CHECK constraint trong models.py. Lệch
nhau thì người dùng nhận 500 từ database thay vì 422 có thông báo rõ ràng.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel, StrictModel
from app.modules.tickets.constants import (
    AiStatus,
    EventType,
    SlaState,
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from app.modules.users.schemas import UserBrief

TITLE = Field(min_length=5, max_length=200)
DESCRIPTION = Field(min_length=10, max_length=5000)


# ─────────────── Input ───────────────

class CreateTicketRequest(StrictModel):
    title: str = TITLE
    description: str = DESCRIPTION
    category_id: UUID | None = Field(default=None, alias="categoryId")
    # Để null thì AI tự phân loại và gán mức ưu tiên (US-19).
    priority: TicketPriority | None = None
    chat_session_id: UUID | None = Field(default=None, alias="chatSessionId")


class UpdateTicketRequest(StrictModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    category_id: UUID | None = Field(default=None, alias="categoryId")
    priority: TicketPriority | None = None
    version: int = Field(ge=1)


class AssignRequest(StrictModel):
    assignee_id: UUID = Field(alias="assigneeId")
    version: int = Field(ge=1)


class ClaimRequest(StrictModel):
    version: int = Field(ge=1)


class ChangeStatusRequest(StrictModel):
    status: TicketStatus
    resolution_note: str | None = Field(
        default=None, alias="resolutionNote", max_length=5000
    )
    version: int = Field(ge=1)


class CreateCommentRequest(StrictModel):
    body: str = Field(min_length=1, max_length=5000)
    # Employee gửi true thì bị BỎ QUA chứ không báo lỗi (BR-10): báo lỗi là
    # tự khai với họ rằng có tồn tại loại bình luận nội bộ.
    is_internal: bool = Field(default=False, alias="isInternal")


# ─────────────── Output ───────────────

class CategoryBrief(ResponseModel):
    id: UUID
    slug: str
    name: str


class TicketListItem(ResponseModel):
    """Bản rút gọn cho danh sách. KHÔNG có `description` — danh sách 20 dòng
    kèm mô tả 5000 ký tự là 100 KB mỗi lần tải trang, không ai đọc."""

    id: UUID
    code: str
    title: str
    status: TicketStatus
    priority: TicketPriority
    category: CategoryBrief | None = None
    requester: UserBrief
    assignee: UserBrief | None = None
    ai_status: AiStatus = Field(serialization_alias="aiStatus")
    sla_state: SlaState | None = Field(default=None, serialization_alias="slaState")
    sla_resolution_due_at: datetime | None = Field(
        default=None, serialization_alias="slaResolutionDueAt"
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    version: int


class TicketResponse(TicketListItem):
    description: str
    source: TicketSource
    resolution_note: str | None = Field(default=None, serialization_alias="resolutionNote")
    sla_response_due_at: datetime | None = Field(
        default=None, serialization_alias="slaResponseDueAt"
    )
    first_response_at: datetime | None = Field(
        default=None, serialization_alias="firstResponseAt"
    )
    resolved_at: datetime | None = Field(default=None, serialization_alias="resolvedAt")
    closed_at: datetime | None = Field(default=None, serialization_alias="closedAt")


class CommentResponse(ResponseModel):
    id: UUID
    body: str
    is_internal: bool = Field(serialization_alias="isInternal")
    author: UserBrief
    created_at: datetime = Field(serialization_alias="createdAt")
    edited_at: datetime | None = Field(default=None, serialization_alias="editedAt")


class EventResponse(ResponseModel):
    """Một dòng trong lịch sử thay đổi (US-17). Bảng chỉ ghi thêm, không sửa."""

    id: UUID
    event_type: EventType = Field(serialization_alias="eventType")
    actor: UserBrief | None = None
    field_name: str | None = Field(default=None, serialization_alias="fieldName")
    old_value: str | None = Field(default=None, serialization_alias="oldValue")
    new_value: str | None = Field(default=None, serialization_alias="newValue")
    created_at: datetime = Field(serialization_alias="createdAt")


class AllowedTransitionsResponse(ResponseModel):
    current_status: TicketStatus = Field(serialization_alias="currentStatus")
    allowed_statuses: list[TicketStatus] = Field(serialization_alias="allowedStatuses")
    version: int


class QueueStatsResponse(ResponseModel):
    """Số đếm cho thanh bên của IT Agent (US-12)."""

    unassigned: int
    assigned_to_me: int = Field(serialization_alias="assignedToMe")
    in_progress: int = Field(serialization_alias="inProgress")
    at_risk: int = Field(serialization_alias="atRisk")
    breached: int
