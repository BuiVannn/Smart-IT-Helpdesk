"""Truy vấn đánh giá sau xử lý. Không chứa logic nghiệp vụ, không commit."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.modules.feedback.models import TicketRating
from app.modules.tickets.models import Ticket


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_ticket(self, ticket_id: UUID) -> TicketRating | None:
        """`ticket_id` là UNIQUE trên bảng — mỗi ticket đúng một đánh giá (BR-06)."""
        return self.session.execute(
            select(TicketRating).where(TicketRating.ticket_id == ticket_id)
        ).scalar_one_or_none()

    def add(self, rating: TicketRating) -> TicketRating:
        self.session.add(rating)
        self.session.flush()
        return rating

    def list_for_agent(self, agent_id: UUID, params: PageParams) -> tuple[list[Row], int]:
        """Đánh giá của các ticket mà `agent_id` xử lý (US-43).

        Nối với `tickets` chỉ để lấy `code`/`title` hiển thị — KHÔNG có
        `rater_id` trong tập cột trả về, đây chính là cách ẩn danh người
        chấm: dữ liệu không bao giờ rời khỏi tầng này chứ không phải bị lọc
        ở schema tầng trên (lọc muộn thì chỉ cần quên một field là lộ).
        """
        base = (
            select(
                TicketRating.id,
                TicketRating.ticket_id,
                Ticket.code,
                Ticket.title,
                TicketRating.score,
                TicketRating.comment,
                TicketRating.created_at,
            )
            .select_from(TicketRating)
            .join(Ticket, Ticket.id == TicketRating.ticket_id)
            .where(TicketRating.agent_id == agent_id)
            .order_by(TicketRating.created_at.desc())
        )

        total = self.session.execute(
            select(func.count()).select_from(TicketRating).where(TicketRating.agent_id == agent_id)
        ).scalar_one()

        rows = self.session.execute(base.offset(params.offset).limit(params.limit)).all()
        return list(rows), int(total)
