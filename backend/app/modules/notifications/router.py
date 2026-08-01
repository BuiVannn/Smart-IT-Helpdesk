"""Endpoint thông báo (US-36).

Mọi endpoint ở đây chỉ thao tác trên thông báo của CHÍNH người đang đăng
nhập — `user_id` được đưa thẳng vào mệnh đề WHERE ở repository, không phải
kiểm tra bằng một câu `if` ở tầng route.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.modules.notifications.schemas import (
    MarkReadResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User

router = APIRouter()


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


@router.get("", response_model=Page[NotificationResponse], summary="Thông báo của tôi")
def list_notifications(
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    params: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> Page[NotificationResponse]:
    items, total = service.list_mine(current_user.id, params, unread_only=unread_only)
    return Page.create([NotificationResponse.model_validate(n) for n in items], total, params)


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Đếm thông báo chưa đọc (frontend polling 30 giây)",
)
def unread_count(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> UnreadCountResponse:
    """★ Đây là endpoint bị gọi nhiều nhất hệ thống: 30 giây/lần × mọi người
    đang online. Giữ nó rẻ — chỉ một `COUNT` chạy trên partial index."""
    return UnreadCountResponse(count=service.unread_count(current_user.id))


@router.post(
    "/{notification_id}/read",
    response_model=MarkReadResponse,
    summary="Đánh dấu một thông báo đã đọc",
)
def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> MarkReadResponse:
    updated = service.mark_read(current_user.id, notification_id)
    # 0 dòng có hai nguyên nhân: thông báo của người khác, hoặc đã đọc rồi.
    # Phân biệt bằng một lần đọc — và trả 404 cho trường hợp đầu, KHÔNG phải
    # 403: 403 tự xác nhận thông báo đó có tồn tại.
    if updated == 0 and service.notifications.get_owned(current_user.id, notification_id) is None:
        raise NotFoundError("Không tìm thấy thông báo")
    return MarkReadResponse(updated=updated)


@router.post("/read-all", response_model=MarkReadResponse, summary="Đánh dấu tất cả đã đọc")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> MarkReadResponse:
    return MarkReadResponse(updated=service.mark_all_read(current_user.id))
