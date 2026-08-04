"""Endpoint ticket (US-08 → US-18).

★ CÒN TRỐNG, THUỘC VỀ NGƯỜI KHÁC — đừng viết chồng lên:
- `POST/GET /tickets/{id}/attachments` (US-09) — cần module storage/MinIO
- `POST /tickets/{id}/rating` (US-41) — Nguyễn Tiến Lưỡng
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.modules.tickets.constants import TicketPriority, TicketStatus
from app.modules.tickets.models import Ticket
from app.modules.tickets.schemas import (
    AiClassificationResponse,
    AllowedTransitionsResponse,
    AssigneeSuggestion,
    AssigneeSuggestionsResponse,
    AssignRequest,
    CategoryBrief,
    ChangeStatusRequest,
    ClaimRequest,
    CommentResponse,
    CreateCommentRequest,
    CreateTicketRequest,
    EventResponse,
    QueueStatsResponse,
    TicketListItem,
    TicketResponse,
    UpdateCommentRequest,
    UpdateTicketRequest,
)
from app.modules.tickets.service import TicketService
from app.modules.users.models import User

router = APIRouter()


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


def _detail(service: TicketService, ticket: Ticket, now: datetime) -> TicketResponse:
    response = TicketResponse.model_validate(ticket)
    response.sla_state = service.sla_state(ticket, now)
    return response


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo ticket (US-08)",
)
def create_ticket(
    data: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponse:
    ticket = service.create(current_user, data)
    return _detail(service, ticket, datetime.now(UTC))


@router.get(
    "",
    response_model=Page[TicketListItem],
    summary="Danh sách ticket, có lọc và tìm kiếm (US-10, US-12, US-16)",
)
def list_tickets(
    params: PageParams = Depends(page_params),
    status_filter: list[TicketStatus] | None = Query(default=None, alias="status"),
    priority: list[TicketPriority] | None = Query(default=None),
    category_id: UUID | None = Query(default=None, alias="categoryId"),
    assignee_id: UUID | None = Query(default=None, alias="assigneeId"),
    mine: bool = Query(default=False, description="Chỉ ticket được giao cho tôi"),
    unassigned: bool = Query(default=False, description="Chỉ ticket chưa có người nhận"),
    q: str | None = Query(default=None, max_length=200, description="Tìm toàn văn"),
    sort_by: str = Query(default="createdAt", alias="sortBy"),
    sort_order: str = Query(default="desc", alias="sortOrder", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> Page[TicketListItem]:
    tickets, total = service.list(
        current_user,
        params,
        status=status_filter,
        priority=priority,
        category_id=category_id,
        assignee_id=assignee_id,
        mine=mine,
        unassigned=unassigned,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    now = datetime.now(UTC)
    items = []
    for ticket in tickets:
        item = TicketListItem.model_validate(ticket)
        item.sla_state = service.sla_state(ticket, now)
        items.append(item)
    return Page.create(items, total, params)


@router.get(
    "/stats/queue",
    response_model=QueueStatsResponse,
    summary="Số đếm hàng chờ của Agent (US-12)",
)
def queue_stats(
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> QueueStatsResponse:
    # Đặt TRƯỚC "/{ticket_id}" trong file này là bắt buộc: nếu để sau,
    # FastAPI sẽ khớp "stats" như một UUID và trả 422.
    return QueueStatsResponse(**service.queue_stats(current_user))


@router.get("/{ticket_id}", response_model=TicketResponse, summary="Chi tiết ticket (US-11)")
def get_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponse:
    ticket = service.get(current_user, ticket_id)
    return _detail(service, ticket, datetime.now(UTC))


@router.patch("/{ticket_id}", response_model=TicketResponse, summary="Sửa ticket")
def update_ticket(
    ticket_id: UUID,
    data: UpdateTicketRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponse:
    ticket = service.update(current_user, ticket_id, data)
    return _detail(service, ticket, datetime.now(UTC))


@router.get(
    "/{ticket_id}/allowed-transitions",
    response_model=AllowedTransitionsResponse,
    summary="Các trạng thái kế tiếp hợp lệ cho vai trò hiện tại",
)
def allowed_transitions(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> AllowedTransitionsResponse:
    # Tồn tại để frontend CHỈ hiển thị nút hợp lệ, thay vì hiện hết rồi báo
    # lỗi. Máy trạng thái vẫn nằm ở backend — frontend chỉ hỏi.
    ticket = service.get(current_user, ticket_id)
    return AllowedTransitionsResponse(
        current_status=ticket.status,
        allowed_statuses=service.allowed_transitions(current_user, ticket_id),
        version=ticket.version,
    )


@router.post("/{ticket_id}/claim", response_model=TicketResponse, summary="Agent tự nhận (US-13)")
def claim_ticket(
    ticket_id: UUID,
    data: ClaimRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponse:
    ticket = service.claim(current_user, ticket_id, data.version)
    return _detail(service, ticket, datetime.now(UTC))


@router.post("/{ticket_id}/assign", response_model=TicketResponse, summary="Giao việc (US-13)")
def assign_ticket(
    ticket_id: UUID,
    data: AssignRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponse:
    ticket = service.assign(current_user, ticket_id, data.assignee_id, data.version)
    return _detail(service, ticket, datetime.now(UTC))


@router.post(
    "/{ticket_id}/status",
    response_model=TicketResponse,
    summary="Chuyển trạng thái / đóng / huỷ (US-14, US-18)",
)
def change_status(
    ticket_id: UUID,
    data: ChangeStatusRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponse:
    ticket = service.change_status(current_user, ticket_id, data)
    return _detail(service, ticket, datetime.now(UTC))


@router.get(
    "/{ticket_id}/comments",
    response_model=list[CommentResponse],
    summary="Bình luận trên ticket (US-15)",
)
def list_comments(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> list[CommentResponse]:
    return service.list_comments(current_user, ticket_id)


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm bình luận (US-15)",
)
def create_comment(
    ticket_id: UUID,
    data: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> CommentResponse:
    return service.add_comment(current_user, ticket_id, data.body, data.is_internal)


@router.patch(
    "/{ticket_id}/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Sửa bình luận (US-15)",
)
def update_comment(
    ticket_id: UUID,
    comment_id: UUID,
    data: UpdateCommentRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> CommentResponse:
    return service.update_comment(current_user, ticket_id, comment_id, data.body)


@router.delete(
    "/{ticket_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xoá bình luận (US-15)",
)
def delete_comment(
    ticket_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> None:
    service.delete_comment(current_user, ticket_id, comment_id)


@router.get(
    "/{ticket_id}/events",
    response_model=list[EventResponse],
    summary="Lịch sử thay đổi (US-17)",
)
def list_events(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> list[EventResponse]:
    return service.list_events(current_user, ticket_id)


@router.get(
    "/{ticket_id}/ai-classification",
    response_model=AiClassificationResponse | None,
    summary="Gợi ý phân loại gần nhất của AI (US-19)",
)
def ai_classification(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> AiClassificationResponse | None:
    """Trả `null` khi AI chưa chạy xong — giao diện hiển thị "Đang phân loại…".

    Tách khỏi `GET /tickets/{id}` có chủ ý: mọi lần mở danh sách hay chi tiết
    ticket sẽ phải gánh thêm một truy vấn cho dữ liệu mà chỉ Agent mới nhìn.
    """
    record = service.latest_ai_classification(current_user, ticket_id)
    return AiClassificationResponse.model_validate(record) if record else None


@router.get(
    "/{ticket_id}/assignee-suggestions",
    response_model=AssigneeSuggestionsResponse,
    summary="Top 3 gợi ý người xử lý theo chuyên môn và tải (US-20)",
)
def assignee_suggestions(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
) -> AssigneeSuggestionsResponse:
    """CHỈ GỢI Ý — không tự giao. Agent trưởng vẫn phải bấm "Giao việc"."""
    now = datetime.now(UTC)
    ticket, suggestions = service.assignee_suggestions(current_user, ticket_id, now=now)
    return AssigneeSuggestionsResponse(
        category=CategoryBrief.model_validate(ticket.category) if ticket.category else None,
        suggestions=[AssigneeSuggestion.model_validate(s) for s in suggestions],
        generated_at=now,
    )
