"""Endpoint đánh giá sau xử lý (F8 — US-41).

★ Mount RIÊNG, không sửa `tickets/router.py` — nơi đó đã chừa sẵn ghi chú
"POST /tickets/{id}/rating (US-41) — Nguyễn Tiến Lưỡng". Router này được
gắn vào cùng prefix `/tickets` từ `app/api/v1/router.py`, chỉ thêm một dòng
`include_router` ở đó.

★ `GET /tickets/ratings/mine` (US-43) ĐĂNG KÝ TRƯỚC `GET /tickets/{ticket_id}/rating`
dù về lý thuyết không va nhau (đoạn cuối khác nhau: "mine" so với một
`ticket_id` bất kỳ theo sau bởi "rating") — vẫn đặt route tĩnh lên trước để
không ai phải nhớ lý do đó khi thêm route mới vào file này.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_agent
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.modules.feedback.schemas import (
    AgentRatingItem,
    CreateRatingRequest,
    RatingResponse,
    UpdateRatingRequest,
)
from app.modules.feedback.service import FeedbackService
from app.modules.users.models import User

router = APIRouter()


def get_feedback_service(db: Session = Depends(get_db)) -> FeedbackService:
    return FeedbackService(db)


@router.get(
    "/ratings/mine",
    response_model=Page[AgentRatingItem],
    summary="Agent xem đánh giá về mình, ẩn danh người chấm (US-43)",
)
def list_my_ratings(
    params: PageParams = Depends(page_params),
    current_user: User = Depends(require_agent),
    service: FeedbackService = Depends(get_feedback_service),
) -> Page[AgentRatingItem]:
    """Chỉ IT Agent/Admin gọi được (`require_agent`); mỗi người chỉ thấy
    đánh giá của ticket CHÍNH MÌNH xử lý — lọc theo `current_user.id` ở
    tầng service, không nhận `agent_id` từ query string."""
    items, total = service.list_my_ratings(current_user, params)
    return Page.create(items, total, params)


@router.post(
    "/{ticket_id}/rating",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đánh giá sau xử lý (US-41)",
)
def create_rating(
    ticket_id: UUID,
    data: CreateRatingRequest,
    current_user: User = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> RatingResponse:
    rating = service.create(current_user, ticket_id, data.score, data.comment)
    return RatingResponse.from_model(rating)


@router.get(
    "/{ticket_id}/rating",
    response_model=RatingResponse,
    summary="Xem đánh giá của ticket",
)
def get_rating(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> RatingResponse:
    rating = service.get(current_user, ticket_id)
    return RatingResponse.from_model(rating)


@router.patch(
    "/{ticket_id}/rating",
    response_model=RatingResponse,
    summary="Sửa đánh giá trong 24 giờ đầu (BR-08)",
)
def update_rating(
    ticket_id: UUID,
    data: UpdateRatingRequest,
    current_user: User = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> RatingResponse:
    rating = service.update(current_user, ticket_id, data.score, data.comment)
    return RatingResponse.from_model(rating)

