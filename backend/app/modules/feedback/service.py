"""FeedbackService — đánh giá sau xử lý (F8 — US-41).

Bảng `ticket_ratings` đã tồn tại sẵn với UNIQUE trên `ticket_id` và CHECK
`score BETWEEN 1 AND 5` (xem `migrations/versions/0002_initial_schema.py`)
— phần khó nhất đã xong ở tầng database. Tầng service ở đây chỉ cần dịch
bốn quy tắc nghiệp vụ sang đúng loại lỗi HTTP.


US-42 (Admin tổng hợp điểm hài lòng) KHÔNG nằm ở đây — đó là báo cáo toàn
hệ thống, thuộc `app/modules/reports/satisfaction.py`, cùng chỗ với các báo
cáo F7 khác.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.pagination import PageParams
from app.modules.feedback.models import TicketRating
from app.modules.feedback.repository import FeedbackRepository
from app.modules.feedback.schemas import AgentRatingItem
from app.modules.tickets.constants import TicketStatus
from app.modules.tickets.models import Ticket
from app.modules.users.models import User

logger = get_logger(__name__)

# Chỉ đánh giá được ticket đã xử lý xong hoặc đã đóng.
RATEABLE_STATUSES = (TicketStatus.RESOLVED, TicketStatus.CLOSED)


class FeedbackService:
    def __init__(self, session: Session) -> None:
        self.db = session
        self.ratings = FeedbackRepository(session)

    def create(self, user: User, ticket_id: UUID, score: int, comment: str | None) -> TicketRating:
        ticket = self._get_ticket_owned(ticket_id, user)

        if ticket.status not in RATEABLE_STATUSES:
            raise ValidationError("Chỉ đánh giá được ticket đã xử lý xong hoặc đã đóng")

        if self.ratings.get_by_ticket(ticket_id) is not None:
            raise ConflictError("Ticket này đã được đánh giá")

        rating = TicketRating(
            ticket_id=ticket_id,
            rater_id=user.id,
            # Bản SAO của assignee LÚC ĐÁNH GIÁ — có chủ đích (xem models.py).
            # Báo cáo hài lòng phải phản ánh đúng người xử lý lúc đó; ticket
            # giao lại về sau không được làm đổi số liệu lịch sử.
            agent_id=ticket.assignee_id,
            score=score,
            comment=comment,
        )
        self.ratings.add(rating)
        self.db.commit()
        logger.info(
            "tạo đánh giá sau xử lý",
            extra={"extra_fields": {"ticket_id": str(ticket_id), "score": score}},
        )
        return rating

    def get(self, user: User, ticket_id: UUID) -> TicketRating:
        self._get_ticket_owned(ticket_id, user)
        rating = self.ratings.get_by_ticket(ticket_id)
        if rating is None:
            raise NotFoundError("Ticket chưa được đánh giá")
        return rating

    def update(self, user: User, ticket_id: UUID, score: int, comment: str | None) -> TicketRating:
        self._get_ticket_owned(ticket_id, user)
        rating = self.ratings.get_by_ticket(ticket_id)
        if rating is None:
            raise NotFoundError("Ticket chưa được đánh giá")

        if not rating.is_editable(datetime.now(UTC)):
            raise ForbiddenError("Đã quá 24 giờ kể từ lúc đánh giá, không thể sửa")

        rating.score = score
        rating.comment = comment
        self.db.commit()
        logger.info(
            "sửa đánh giá sau xử lý",
            extra={"extra_fields": {"ticket_id": str(ticket_id), "score": score}},
        )
        return rating

    def list_my_ratings(self, agent: User, params: PageParams) -> tuple[list[AgentRatingItem], int]:
        """Agent xem đánh giá về mình, ẩn danh người chấm (US-43).

        Lọc theo `agent.id` ngay ở tầng repository — không có tham số nào
        cho phép xem đánh giá của người khác, nên router chỉ cần gắn
        `require_agent` là đủ, không cần thêm kiểm tra quyền ở đây.
        """
        rows, total = self.ratings.list_for_agent(agent.id, params)
        items = [
            AgentRatingItem(
                id=rating_id,
                ticket_id=ticket_id,
                ticket_code=ticket_code,
                ticket_title=ticket_title,
                score=score,
                comment=comment,
                created_at=created_at,
            )
            for rating_id, ticket_id, ticket_code, ticket_title, score, comment, created_at in rows
        ]
        return items, total

    def _get_ticket_owned(self, ticket_id: UUID, user: User) -> Ticket:
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            logger.warning(f"Ticket {ticket_id} not found")
            raise NotFoundError("Không tìm thấy ticket")

        # ★ Chuyển cả hai về chuỗi để so sánh an toàn, tránh lỗi kiểu dữ liệu
        if str(ticket.requester_id) != str(user.id):
            logger.warning(
                f"Requester mismatch: ticket.requester_id={ticket.requester_id} "
                f"(type: {type(ticket.requester_id)}), "
                f"user.id={user.id} (type: {type(user.id)})"
            )
            raise NotFoundError("Không tìm thấy ticket")
        return ticket
