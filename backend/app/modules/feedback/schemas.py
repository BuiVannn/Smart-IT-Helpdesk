"""Schema của module đánh giá sau xử lý (F8 — US-41)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel, StrictModel

if TYPE_CHECKING:
    from app.modules.feedback.models import TicketRating


class CreateRatingRequest(StrictModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class UpdateRatingRequest(StrictModel):
    """Sửa đánh giá — chỉ trong 24 giờ đầu (BR-08), xem `TicketRating.is_editable`."""

    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class RatingResponse(ResponseModel):
    """★ `isEditable` là hàm (`TicketRating.is_editable()`), không phải cột,
    nên KHÔNG dùng `model_validate(rating)` trực tiếp — `from_attributes`
    không tự gọi được hàm. Luôn dựng qua `from_model()`.
    """

    id: UUID
    ticket_id: UUID = Field(serialization_alias="ticketId")
    score: int
    comment: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
    is_editable: bool = Field(serialization_alias="isEditable")

    @classmethod
    def from_model(cls, rating: "TicketRating") -> "RatingResponse":
        return cls(
            id=rating.id,
            ticket_id=rating.ticket_id,
            score=rating.score,
            comment=rating.comment,
            created_at=rating.created_at,
            is_editable=rating.is_editable(),
        )
        

class AgentRatingItem(ResponseModel):
    """Một đánh giá trong danh sách "đánh giá về tôi" của Agent (US-43).
 
    ★ CỐ Ý KHÔNG có trường nào định danh người chấm — không `raterId`, không
    `raterName`. AC của US-43 yêu cầu ẩn danh; repository tầng dưới còn không
    truy vấn `rater_id`, nên không có gì để lộ dù schema này có lỗi.
    """
 
    id: UUID = Field(serialization_alias="ratingId")
    ticket_id: UUID = Field(serialization_alias="ticketId")
    ticket_code: str = Field(serialization_alias="ticketCode")
    ticket_title: str = Field(serialization_alias="ticketTitle")
    score: int
    comment: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
           