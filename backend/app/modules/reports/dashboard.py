"""Báo cáo vận hành cho dashboard (F7 — US-37, US-38, US-39, US-40).

Tách khỏi `service.py` (nơi có báo cáo độ chính xác AI) vì hai nhóm trả lời
hai câu hỏi khác nhau: ở đây là "đội IT đang chạy thế nào", ở kia là "AI phân
loại có dùng được không".

★ MỌI CHỈ SỐ THỜI GIAN Ở ĐÂY DÙNG TRUNG VỊ (p50) VÀ p90, KHÔNG DÙNG TRUNG
BÌNH — đúng yêu cầu US-38. Một ticket bị bỏ quên ba tuần sẽ kéo trung bình
lên gấp đôi và làm cả báo cáo vô nghĩa, trong khi trung vị gần như không đổi.
Trung bình vẫn được trả ở báo cáo workload vì ở đó nó dùng để so sánh tương
đối giữa các Agent, không dùng để cam kết với ai.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.orm import Session

from app.modules.feedback.models import TicketRating
from app.modules.tickets.constants import (
    OPEN_STATUSES,
    EventType,
    TicketPriority,
    TicketStatus,
)
from app.modules.tickets.models import Ticket, TicketCategory, TicketEvent
from app.modules.users.constants import UserRole
from app.modules.users.models import User

DEFAULT_WINDOW_DAYS = 30
MAX_EXPORT_ROWS = 10_000

# Nhãn tiếng Việt cho biểu đồ. Để ở backend chứ không ở frontend: cùng một
# bộ nhãn dùng cho cả biểu đồ lẫn file CSV xuất ra, và CSV thì không đi qua
# frontend.
STATUS_LABELS: dict[str, str] = {
    TicketStatus.NEW: "Mới",
    TicketStatus.ASSIGNED: "Đã giao",
    TicketStatus.IN_PROGRESS: "Đang xử lý",
    TicketStatus.PENDING_REQUESTER: "Chờ người yêu cầu",
    TicketStatus.RESOLVED: "Đã xử lý",
    TicketStatus.CLOSED: "Đã đóng",
    TicketStatus.CANCELLED: "Đã huỷ",
}

PRIORITY_LABELS: dict[str, str] = {
    TicketPriority.LOW: "Thấp",
    TicketPriority.MEDIUM: "Trung bình",
    TicketPriority.HIGH: "Cao",
    TicketPriority.URGENT: "Khẩn cấp",
}


@dataclass
class CountBucket:
    key: str
    label: str
    count: int


@dataclass
class OverviewReport:
    from_at: datetime
    to_at: datetime
    total: int = 0
    open_total: int = 0
    resolved_total: int = 0
    breached_total: int = 0
    unassigned_total: int = 0
    by_status: list[CountBucket] = field(default_factory=list)
    by_priority: list[CountBucket] = field(default_factory=list)
    by_category: list[CountBucket] = field(default_factory=list)
    daily: list[CountBucket] = field(default_factory=list)

    @property
    def breach_rate(self) -> float | None:
        """`None` chứ không phải 0 khi chưa có ticket nào — "chưa đủ dữ liệu"
        và "không vi phạm lần nào" là hai điều khác hẳn nhau."""
        return round(self.breached_total / self.total, 4) if self.total else None


@dataclass
class DurationRow:
    key: str
    label: str
    tickets: int
    first_response_p50: float | None = None
    first_response_p90: float | None = None
    resolution_p50: float | None = None
    resolution_p90: float | None = None


@dataclass
class AgentWorkloadRow:
    agent_id: UUID
    agent_name: str
    open_tickets: int = 0
    urgent_open: int = 0
    resolved_in_period: int = 0
    avg_resolution_minutes: float | None = None
    sla_breached: int = 0
    avg_rating: float | None = None
    rating_count: int = 0

    @property
    def sla_breach_rate(self) -> float | None:
        return (
            round(self.sla_breached / self.resolved_in_period, 4)
            if self.resolved_in_period
            else None
        )


class DashboardService:
    """Truy vấn tổng hợp cho dashboard. Không sửa dữ liệu, không commit."""

    def __init__(self, session: Session) -> None:
        self.db = session

    # ── Khung thời gian ───────────────────────────────────────────────

    @staticmethod
    def resolve_window(
        from_at: datetime | None, to_at: datetime | None
    ) -> tuple[datetime, datetime]:
        """Mặc định 30 ngày gần nhất (US-37).

        Đảo lại nếu người gọi truyền ngược: một khoảng rỗng trả về báo cáo
        toàn số 0 trông y hệt "không có việc gì xảy ra", và không ai nhận ra
        mình vừa gõ nhầm ngày.
        """
        end = to_at or datetime.now(UTC)
        start = from_at or (end - timedelta(days=DEFAULT_WINDOW_DAYS))
        return (end, start) if start > end else (start, end)

    # ── US-37: Tổng quan ──────────────────────────────────────────────

    def overview(self, from_at: datetime, to_at: datetime) -> OverviewReport:
        report = OverviewReport(from_at=from_at, to_at=to_at)
        window = self._created_within(from_at, to_at)

        for status, count in self.db.execute(
            select(Ticket.status, func.count()).where(window).group_by(Ticket.status)
        ).all():
            report.by_status.append(
                CountBucket(
                    key=str(status),
                    label=STATUS_LABELS.get(status, str(status)),
                    count=count,
                )
            )
            report.total += count
            if status in OPEN_STATUSES:
                report.open_total += count
            if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                report.resolved_total += count

        # Giữ thứ tự nghiệp vụ (Mới → Đã đóng), không phải thứ tự chữ cái —
        # biểu đồ cột mà cột "Đã đóng" đứng trước "Đang xử lý" là biểu đồ khó đọc.
        order = list(STATUS_LABELS)
        report.by_status.sort(key=lambda b: order.index(b.key) if b.key in order else 99)

        for priority, count in self.db.execute(
            select(Ticket.priority, func.count()).where(window).group_by(Ticket.priority)
        ).all():
            report.by_priority.append(
                CountBucket(
                    key=str(priority),
                    label=PRIORITY_LABELS.get(priority, str(priority)),
                    count=count,
                )
            )
        priority_order = list(PRIORITY_LABELS)
        report.by_priority.sort(
            key=lambda b: priority_order.index(b.key) if b.key in priority_order else 99,
            reverse=True,
        )

        for slug, name, count in self.db.execute(
            select(
                func.coalesce(TicketCategory.slug, "unclassified"),
                func.coalesce(TicketCategory.name, "Chưa phân loại"),
                func.count(),
            )
            .select_from(Ticket)
            .outerjoin(TicketCategory, TicketCategory.id == Ticket.category_id)
            .where(window)
            .group_by(TicketCategory.slug, TicketCategory.name)
            .order_by(func.count().desc())
        ).all():
            report.by_category.append(CountBucket(key=slug, label=name, count=count))

        # Vi phạm SLA: đã quá hạn mà chưa xử lý xong, HOẶC xử lý xong sau hạn.
        # Điều kiện thứ hai hay bị quên, và quên nó thì tỉ lệ vi phạm tự "đẹp"
        # lên mỗi khi Agent đóng nốt các ticket đã trễ.
        report.breached_total = self.db.execute(
            select(func.count())
            .select_from(Ticket)
            .where(
                window,
                Ticket.sla_resolution_due_at.is_not(None),
                case(
                    (Ticket.resolved_at.is_(None), Ticket.sla_resolution_due_at < func.now()),
                    else_=Ticket.resolved_at > Ticket.sla_resolution_due_at,
                ),
            )
        ).scalar_one()

        report.unassigned_total = self.db.execute(
            select(func.count())
            .select_from(Ticket)
            .where(window, Ticket.assignee_id.is_(None), Ticket.status.in_(OPEN_STATUSES))
        ).scalar_one()

        for day, count in self.db.execute(
            select(func.date_trunc("day", Ticket.created_at).label("day"), func.count())
            .where(window)
            .group_by("day")
            .order_by("day")
        ).all():
            report.daily.append(
                CountBucket(key=day.date().isoformat(), label=day.strftime("%d/%m"), count=count)
            )

        return report

    # ── US-38: Thời gian xử lý ────────────────────────────────────────

    def resolution_time(self, from_at: datetime, to_at: datetime) -> list[DurationRow]:
        """Trung vị và p90 của thời gian phản hồi đầu tiên và thời gian xử lý.

        ★ Thời gian xử lý ĐÃ TRỪ khoảng ticket nằm ở `PENDING_REQUESTER`
        (US-38, và quy tắc 2 của tài liệu 03 §6): chờ người dùng gửi ảnh chụp
        màn hình không phải lỗi của Agent.

        Khoảng chờ được tính lại từ `ticket_events` chứ KHÔNG đọc cột
        `tickets.paused_seconds`: cột đó hiện chưa có đường ghi nào nên luôn
        bằng 0, và một báo cáo dựa vào nó sẽ im lặng cho ra số sai. Nhật ký
        sự kiện là chỉ-ghi-thêm nên nó là nguồn đáng tin duy nhất ở đây.

        Thời gian phản hồi đầu tiên KHÔNG trừ khoảng chờ: theo định nghĩa nó
        kết thúc trước khi ticket kịp vào trạng thái chờ người dùng.
        """
        pauses = self._pause_seconds_subquery()

        # `greatest(..., 0)`: đồng hồ máy chủ nhảy lùi hoặc dữ liệu cũ nhập tay
        # có thể cho ra số âm, và một trung vị âm sẽ khiến người đọc mất lòng
        # tin vào cả bảng.
        resolution_seconds = func.greatest(
            func.extract("epoch", Ticket.resolved_at - Ticket.created_at)
            - func.coalesce(pauses.c.paused_seconds, 0),
            0,
        )
        first_response_seconds = func.greatest(
            func.extract("epoch", Ticket.first_response_at - Ticket.created_at), 0
        )

        stmt = (
            select(
                func.coalesce(TicketCategory.slug, "unclassified").label("key"),
                func.coalesce(TicketCategory.name, "Chưa phân loại").label("label"),
                func.count().label("tickets"),
                func.percentile_cont(0.5)
                .within_group(first_response_seconds.asc())
                .filter(Ticket.first_response_at.is_not(None))
                .label("fr_p50"),
                func.percentile_cont(0.9)
                .within_group(first_response_seconds.asc())
                .filter(Ticket.first_response_at.is_not(None))
                .label("fr_p90"),
                func.percentile_cont(0.5).within_group(resolution_seconds.asc()).label("res_p50"),
                func.percentile_cont(0.9).within_group(resolution_seconds.asc()).label("res_p90"),
            )
            .select_from(Ticket)
            .outerjoin(TicketCategory, TicketCategory.id == Ticket.category_id)
            .outerjoin(pauses, pauses.c.ticket_id == Ticket.id)
            .where(
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at >= from_at,
                Ticket.resolved_at <= to_at,
            )
            .group_by(TicketCategory.slug, TicketCategory.name)
            .order_by(func.count().desc())
        )

        return [
            DurationRow(
                key=row.key,
                label=row.label,
                tickets=row.tickets,
                first_response_p50=_to_minutes(row.fr_p50),
                first_response_p90=_to_minutes(row.fr_p90),
                resolution_p50=_to_minutes(row.res_p50),
                resolution_p90=_to_minutes(row.res_p90),
            )
            for row in self.db.execute(stmt).all()
        ]

    def _pause_seconds_subquery(self):
        """Tổng thời gian mỗi ticket nằm ở `PENDING_REQUESTER`.

        Dùng `LEAD` trên nhật ký trạng thái: mỗi lần vào `PENDING_REQUESTER`
        kéo dài tới sự kiện đổi trạng thái KẾ TIẾP. Ticket còn đang chờ (không
        có sự kiện kế tiếp) tính tới thời điểm hiện tại.

        Sắp xếp thêm theo `id` bên cạnh `created_at`: `created_at` do
        `transaction_timestamp()` sinh ra nên hai sự kiện ghi trong cùng một
        transaction có mốc giống hệt nhau, và `LEAD` sẽ ghép sai cặp. `id` là
        UUIDv7 nên tự đúng thứ tự thời gian.
        """
        events = (
            select(
                TicketEvent.ticket_id.label("ticket_id"),
                TicketEvent.created_at.label("started_at"),
                TicketEvent.new_value.label("new_value"),
                func.lead(TicketEvent.created_at)
                .over(
                    partition_by=TicketEvent.ticket_id,
                    order_by=(TicketEvent.created_at, TicketEvent.id),
                )
                .label("next_at"),
            )
            .where(TicketEvent.event_type == EventType.STATUS_CHANGED)
            .subquery()
        )

        return (
            select(
                events.c.ticket_id.label("ticket_id"),
                func.sum(
                    func.extract(
                        "epoch",
                        func.coalesce(events.c.next_at, func.now()) - events.c.started_at,
                    )
                ).label("paused_seconds"),
            )
            .where(events.c.new_value == TicketStatus.PENDING_REQUESTER.value)
            .group_by(events.c.ticket_id)
            .subquery()
        )

    # ── US-39: Workload theo Agent ────────────────────────────────────

    def agent_workload(self, from_at: datetime, to_at: datetime) -> list[AgentWorkloadRow]:
        """Mỗi Agent một dòng, kể cả Agent chưa có việc nào.

        ★ Bốn truy vấn nhỏ rồi ghép trong Python, KHÔNG phải một câu JOIN lớn.
        Lý do: "đang mở" đếm theo trạng thái hiện tại còn "đã xử lý trong kỳ"
        đếm theo `resolved_at`, hai điều kiện lọc khác nhau trên cùng một
        bảng. Gộp vào một JOIN sẽ nhân chéo số dòng và cho ra số đếm phồng
        lên — lỗi này rất khó nhận ra vì kết quả vẫn "trông hợp lý".

        Agent chưa từng nhận việc vẫn phải xuất hiện với số 0: bảng workload
        mà thiếu người rảnh thì không dùng để cân đối phân công được.
        """
        agents = {
            row.id: AgentWorkloadRow(agent_id=row.id, agent_name=row.full_name)
            for row in self.db.execute(
                select(User.id, User.full_name)
                .where(User.role == UserRole.IT_AGENT, User.is_active.is_(True))
                .order_by(User.full_name)
            ).all()
        }

        def row_for(agent_id: UUID) -> AgentWorkloadRow | None:
            # Ticket của Agent đã bị khoá vẫn nằm trong DB nhưng không hiện ở
            # bảng này — bỏ qua thay vì tạo dòng "ma" không có tên.
            return agents.get(agent_id)

        for agent_id, count, urgent in self.db.execute(
            select(
                Ticket.assignee_id,
                func.count(),
                func.count().filter(Ticket.priority == TicketPriority.URGENT),
            )
            .where(Ticket.assignee_id.is_not(None), Ticket.status.in_(OPEN_STATUSES))
            .group_by(Ticket.assignee_id)
        ).all():
            if (row := row_for(agent_id)) is not None:
                row.open_tickets = count
                row.urgent_open = urgent

        pauses = self._pause_seconds_subquery()
        resolution_seconds = func.greatest(
            func.extract("epoch", Ticket.resolved_at - Ticket.created_at)
            - func.coalesce(pauses.c.paused_seconds, 0),
            0,
        )

        for agent_id, count, avg_seconds, breached in self.db.execute(
            select(
                Ticket.assignee_id,
                func.count(),
                func.avg(resolution_seconds),
                func.count().filter(
                    and_(
                        Ticket.sla_resolution_due_at.is_not(None),
                        Ticket.resolved_at > Ticket.sla_resolution_due_at,
                    )
                ),
            )
            .select_from(Ticket)
            .outerjoin(pauses, pauses.c.ticket_id == Ticket.id)
            .where(
                Ticket.assignee_id.is_not(None),
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at >= from_at,
                Ticket.resolved_at <= to_at,
            )
            .group_by(Ticket.assignee_id)
        ).all():
            if (row := row_for(agent_id)) is not None:
                row.resolved_in_period = count
                row.avg_resolution_minutes = _to_minutes(avg_seconds)
                row.sla_breached = breached

        # Điểm hài lòng lấy từ `ticket_ratings.agent_id` — bản sao của assignee
        # tại thời điểm đánh giá. Dùng `tickets.assignee_id` sẽ gán điểm cho
        # người nhận bàn giao về sau, không phải người thật sự bị chấm.
        for agent_id, avg_score, count in self.db.execute(
            select(TicketRating.agent_id, func.avg(TicketRating.score), func.count())
            .where(
                TicketRating.agent_id.is_not(None),
                TicketRating.created_at >= from_at,
                TicketRating.created_at <= to_at,
            )
            .group_by(TicketRating.agent_id)
        ).all():
            if (row := row_for(agent_id)) is not None:
                row.avg_rating = round(float(avg_score), 2) if avg_score is not None else None
                row.rating_count = count

        return list(agents.values())

    # ── US-40: Xuất CSV ───────────────────────────────────────────────

    def export_rows(self, from_at: datetime, to_at: datetime, limit: int = MAX_EXPORT_ROWS):
        """Sinh từng dòng ticket để ghi ra CSV — KHÔNG nạp hết vào bộ nhớ.

        `yield_per` bảo SQLAlchemy dùng con trỏ phía server: 10.000 ticket
        chảy qua từng lô 500 dòng thay vì nằm cùng lúc trong RAM. Đây là điều
        kiện để `StreamingResponse` thật sự stream chứ không chỉ trông giống.
        """
        stmt: Select = (
            select(
                Ticket.code,
                Ticket.title,
                Ticket.status,
                Ticket.priority,
                func.coalesce(TicketCategory.name, ""),
                func.coalesce(User.full_name, ""),
                Ticket.created_at,
                Ticket.resolved_at,
                Ticket.sla_resolution_due_at,
            )
            .select_from(Ticket)
            .outerjoin(TicketCategory, TicketCategory.id == Ticket.category_id)
            .outerjoin(User, User.id == Ticket.assignee_id)
            .where(self._created_within(from_at, to_at))
            .order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .limit(limit)
        )
        return self.db.execute(stmt.execution_options(yield_per=500))

    # ── Dùng chung ────────────────────────────────────────────────────

    @staticmethod
    def _created_within(from_at: datetime, to_at: datetime):
        return and_(Ticket.created_at >= from_at, Ticket.created_at <= to_at)


def _to_minutes(seconds: float | None) -> float | None:
    """Đổi giây sang phút, giữ một chữ số thập phân.

    `None` được giữ nguyên là `None`: không có ticket nào để đo khác hẳn với
    "đo được 0 phút", và biểu đồ phải phân biệt được hai trường hợp đó.
    """
    return round(float(seconds) / 60, 1) if seconds is not None else None
