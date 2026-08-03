"""Truy vấn đánh giá sau xử lý. Không chứa logic nghiệp vụ, không commit."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.feedback.models import TicketRating


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
    