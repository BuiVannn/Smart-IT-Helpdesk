"""Báo cáo tổng hợp điểm hài lòng (F8 — US-42).

Trả lời câu hỏi "chất lượng dịch vụ đang thế nào", tách theo Agent, theo loại
sự cố, theo tháng — dữ liệu đưa vào báo cáo đánh giá hiệu suất của Admin.

★ MẪU SỐ CỦA `response_rate` LÀ TICKET ĐÃ ĐÓNG, KHÔNG PHẢI TỔNG SỐ TICKET.
Nhân viên chỉ đánh giá được ticket `RESOLVED`/`CLOSED` (US-41) — lấy tổng số
ticket làm mẫu số sẽ khiến tỉ lệ phản hồi trông thấp giả tạo vì lẫn cả những
ticket còn đang mở, chưa ai có cơ hội đánh giá.

★ ĐIỂM TRUNG BÌNH MÀ THIẾU TỈ LỆ PHẢN HỒI THÌ KHÔNG ĐÁNG TIN (US-42, AC 2):
một Agent với avg 5.0 nhưng chỉ 1/40 ticket được đánh giá không đáng so sánh
với một Agent avg 4.2 nhưng 30/40 ticket có đánh giá — báo cáo LUÔN trả kèm
`response_rate` để người đọc tự cân nhắc, không tự ý lọc bớt theo ngưỡng nào.

★ GOM THEO `ticket_ratings.agent_id`, KHÔNG PHẢI `tickets.assignee_id` — lý
do giống hệt `dashboard.py::agent_workload`: đây là bản sao người xử lý TẠI
THỜI ĐIỂM đánh giá, để ticket giao lại về sau không làm đổi số liệu lịch sử.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.feedback.models import TicketRating
from app.modules.tickets.constants import TicketStatus
from app.modules.tickets.models import Ticket, TicketCategory
from app.modules.users.models import User

CLOSED_STATUSES = (TicketStatus.RESOLVED, TicketStatus.CLOSED)
SCORES = (1, 2, 3, 4, 5)


@dataclass
class SatisfactionBucket:
    """Một dòng trong bảng: toàn hệ thống, một Agent, một loại sự cố, hoặc
    một tháng — cùng một hình dạng để router chỉ cần một hàm chuyển đổi."""

    key: str
    label: str
    rating_count: int = 0
    avg_score: float | None = None
    distribution: dict[int, int] = field(default_factory=lambda: dict.fromkeys(SCORES, 0))
    closed_tickets: int = 0

    @property
    def response_rate(self) -> float | None:
        """`None` khi chưa có ticket nào đã đóng trong kỳ — "chưa đủ dữ liệu"
        khác hẳn "không ai đánh giá cả", và hai điều đó không được lẫn vào 0."""
        return round(self.rating_count / self.closed_tickets, 4) if self.closed_tickets else None


@dataclass
class SatisfactionReport:
    from_at: datetime
    to_at: datetime
    overall: SatisfactionBucket
    by_agent: list[SatisfactionBucket] = field(default_factory=list)
    by_category: list[SatisfactionBucket] = field(default_factory=list)
    by_month: list[SatisfactionBucket] = field(default_factory=list)


class SatisfactionService:
    """Truy vấn tổng hợp cho báo cáo hài lòng. Không sửa dữ liệu, không commit."""

    def __init__(self, session: Session) -> None:
        self.db = session

    def report(self, from_at: datetime, to_at: datetime) -> SatisfactionReport:
        overall = SatisfactionBucket(key="overall", label="Toàn hệ thống")
        self._fill_rating_stats(overall, self._rating_window_totals(from_at, to_at))
        overall.closed_tickets = self._closed_tickets_total(from_at, to_at)

        return SatisfactionReport(
            from_at=from_at,
            to_at=to_at,
            overall=overall,
            by_agent=self._by_agent(from_at, to_at),
            by_category=self._by_category(from_at, to_at),
            by_month=self._by_month(from_at, to_at),
        )

    # ── Cột đếm điểm dùng chung cho mọi truy vấn ─────────────────────────

    @staticmethod
    def _score_count_columns():
        """5 cột đếm — một cho mỗi mức sao — dùng lại ở cả bốn truy vấn bên
        dưới. Đếm bằng `FILTER` trong một lượt quét thay vì 5 truy vấn con."""
        return [func.count().filter(TicketRating.score == s) for s in SCORES]

    def _fill_rating_stats(self, bucket: SatisfactionBucket, row) -> None:
        count, avg_score, *dist = row
        bucket.rating_count = int(count)
        bucket.avg_score = round(float(avg_score), 2) if avg_score is not None else None
        bucket.distribution = dict(zip(SCORES, (int(d) for d in dist), strict=True))

    def _rating_window_totals(self, from_at: datetime, to_at: datetime):
        row = self.db.execute(
            select(
                func.count(),
                func.avg(TicketRating.score),
                *self._score_count_columns(),
            ).where(TicketRating.created_at >= from_at, TicketRating.created_at <= to_at)
        ).fetchone()
        return tuple(row) if row is not None else (0, None, 0, 0, 0, 0, 0)

    def _closed_tickets_total(self, from_at: datetime, to_at: datetime) -> int:
        """Ticket đã xử lý xong trong kỳ — mẫu số của tỉ lệ phản hồi.

        Dùng `resolved_at` chứ không `created_at`: một ticket tạo cuối kỳ
        trước, đóng đầu kỳ này thì cơ hội đánh giá thuộc về kỳ đóng, không
        phải kỳ tạo — cùng lựa chọn với `resolved_in_period` ở dashboard.py.
        """
        return self.db.execute(
            select(func.count())
            .select_from(Ticket)
            .where(
                Ticket.status.in_(CLOSED_STATUSES),
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at >= from_at,
                Ticket.resolved_at <= to_at,
            )
        ).scalar_one()

    # ── Theo Agent ────────────────────────────────────────────────────

    def _by_agent(self, from_at: datetime, to_at: datetime) -> list[SatisfactionBucket]:
        buckets: dict[str, SatisfactionBucket] = {}

        rating_rows = self.db.execute(
            select(
                TicketRating.agent_id,
                User.full_name,
                func.count(),
                func.avg(TicketRating.score),
                *self._score_count_columns(),
            )
            .select_from(TicketRating)
            .join(User, User.id == TicketRating.agent_id)
            .where(
                TicketRating.agent_id.is_not(None),
                TicketRating.created_at >= from_at,
                TicketRating.created_at <= to_at,
            )
            .group_by(TicketRating.agent_id, User.full_name)
        ).all()

        for agent_id, full_name, count, avg_score, *dist in rating_rows:
            bucket = SatisfactionBucket(key=str(agent_id), label=full_name)
            self._fill_rating_stats(bucket, (count, avg_score, *dist))
            buckets[str(agent_id)] = bucket

        closed_rows = self.db.execute(
            select(Ticket.assignee_id, User.full_name, func.count())
            .select_from(Ticket)
            .join(User, User.id == Ticket.assignee_id)
            .where(
                Ticket.assignee_id.is_not(None),
                Ticket.status.in_(CLOSED_STATUSES),
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at >= from_at,
                Ticket.resolved_at <= to_at,
            )
            .group_by(Ticket.assignee_id, User.full_name)
        ).all()

        for agent_id, full_name, count in closed_rows:
            bucket = buckets.setdefault(
                str(agent_id), SatisfactionBucket(key=str(agent_id), label=full_name)
            )
            bucket.closed_tickets = int(count)

        return sorted(buckets.values(), key=lambda b: b.label)

    # ── Theo loại sự cố ───────────────────────────────────────────────

    def _by_category(self, from_at: datetime, to_at: datetime) -> list[SatisfactionBucket]:
        """Đánh giá gắn với TICKET, không có cột category riêng — phải nối
        qua `tickets.category_id`. Ticket chưa phân loại gom vào một dòng
        "Chưa phân loại" thay vì bị lặng lẽ loại khỏi báo cáo."""
        buckets: dict[str, SatisfactionBucket] = {}

        rating_rows = self.db.execute(
            select(
                func.coalesce(TicketCategory.slug, "unclassified"),
                func.coalesce(TicketCategory.name, "Chưa phân loại"),
                func.count(),
                func.avg(TicketRating.score),
                *self._score_count_columns(),
            )
            .select_from(TicketRating)
            .join(Ticket, Ticket.id == TicketRating.ticket_id)
            .outerjoin(TicketCategory, TicketCategory.id == Ticket.category_id)
            .where(TicketRating.created_at >= from_at, TicketRating.created_at <= to_at)
            .group_by(TicketCategory.slug, TicketCategory.name)
        ).all()

        for slug, name, count, avg_score, *dist in rating_rows:
            bucket = SatisfactionBucket(key=slug, label=name)
            self._fill_rating_stats(bucket, (count, avg_score, *dist))
            buckets[slug] = bucket

        closed_rows = self.db.execute(
            select(
                func.coalesce(TicketCategory.slug, "unclassified"),
                func.coalesce(TicketCategory.name, "Chưa phân loại"),
                func.count(),
            )
            .select_from(Ticket)
            .outerjoin(TicketCategory, TicketCategory.id == Ticket.category_id)
            .where(
                Ticket.status.in_(CLOSED_STATUSES),
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at >= from_at,
                Ticket.resolved_at <= to_at,
            )
            .group_by(TicketCategory.slug, TicketCategory.name)
        ).all()

        for slug, name, count in closed_rows:
            bucket = buckets.setdefault(slug, SatisfactionBucket(key=slug, label=name))
            bucket.closed_tickets = int(count)

        return sorted(buckets.values(), key=lambda b: b.closed_tickets, reverse=True)

    # ── Theo tháng ────────────────────────────────────────────────────

    def _by_month(self, from_at: datetime, to_at: datetime) -> list[SatisfactionBucket]:
        buckets: dict[str, SatisfactionBucket] = {}

        rating_month = func.date_trunc("month", TicketRating.created_at).label("month")
        rating_rows = self.db.execute(
            select(
                rating_month,
                func.count(),
                func.avg(TicketRating.score),
                *self._score_count_columns(),
            )
            .where(TicketRating.created_at >= from_at, TicketRating.created_at <= to_at)
            .group_by(rating_month)
        ).all()

        for month, count, avg_score, *dist in rating_rows:
            key = month.date().isoformat()
            bucket = SatisfactionBucket(key=key, label=f"Tháng {month:%m/%Y}")
            self._fill_rating_stats(bucket, (count, avg_score, *dist))
            buckets[key] = bucket

        closed_month = func.date_trunc("month", Ticket.resolved_at).label("month")
        closed_rows = self.db.execute(
            select(closed_month, func.count())
            .select_from(Ticket)
            .where(
                Ticket.status.in_(CLOSED_STATUSES),
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at >= from_at,
                Ticket.resolved_at <= to_at,
            )
            .group_by(closed_month)
        ).all()

        for month, count in closed_rows:
            key = month.date().isoformat()
            bucket = buckets.setdefault(
                key, SatisfactionBucket(key=key, label=f"Tháng {month:%m/%Y}")
            )
            bucket.closed_tickets = int(count)

        return sorted(buckets.values(), key=lambda b: b.key)
    
    