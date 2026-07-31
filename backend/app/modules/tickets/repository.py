"""Truy vấn ticket.

★ MỌI truy vấn danh sách/chi tiết BẮT BUỘC nhận `visible` — điều kiện WHERE
do TicketAccessPolicy sinh ra. Không có đường nào đọc ticket mà bỏ qua nó.
Lọc trong SQL chứ không lấy hết rồi lọc bằng Python: lọc sau làm `totalItems`
sai (lộ tổng số ticket toàn hệ thống) và chỉ cần một chỗ quên là rò rỉ dữ liệu.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.pagination import PageParams
from app.modules.tickets.constants import OPEN_STATUSES, TicketPriority, TicketStatus
from app.modules.tickets.models import Ticket, TicketComment, TicketEvent
from app.modules.tickets.sla import AT_RISK_RATIO

# `simple` + unaccent: PostgreSQL không có bộ phân tích hình thái tiếng Việt,
# nhưng unaccent cho phép gõ "mat khau" tìm ra "mật khẩu" (xem migration 0004).
SEARCH_CONDITION = text(
    "tickets.search_vector @@ plainto_tsquery('simple', immutable_unaccent(:q))"
)

SORTABLE = {
    "createdAt": Ticket.created_at,
    "updatedAt": Ticket.updated_at,
    "priority": Ticket.priority,
    "status": Ticket.status,
    "slaResolutionDueAt": Ticket.sla_resolution_due_at,
}


class TicketRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Ghi ───────────────────────────────────────────────────────────

    def next_code(self) -> str:
        """Sinh mã dạng HD-YYYYMM-NNNNN (BR-20).

        Dùng SEQUENCE của PostgreSQL chứ KHÔNG dùng `SELECT max(code) + 1`:
        max+1 sẽ cấp trùng mã khi hai người tạo ticket cùng lúc, và mã ticket
        trùng nhau là thứ không sửa được sau khi người dùng đã đọc nó.
        """
        number = self.session.execute(select(func.nextval("ticket_code_seq"))).scalar_one()
        return f"HD-{datetime.now(UTC):%Y%m}-{number:05d}"

    def add(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        self.session.flush()
        return ticket

    # ── Đọc ───────────────────────────────────────────────────────────

    def _with_relations(self, stmt: Select) -> Select:
        """Nạp sẵn quan hệ để tránh N+1.

        Danh sách 20 ticket mà lười nạp là 61 truy vấn thay vì 1.
        """
        return stmt.options(
            selectinload(Ticket.requester),
            selectinload(Ticket.assignee),
            selectinload(Ticket.category),
        )

    def get(self, ticket_id: UUID, visible: ColumnElement[bool]) -> Ticket | None:
        stmt = self._with_relations(
            select(Ticket).where(Ticket.id == ticket_id, visible)
        # ★ populate_existing là BẮT BUỘC ở đây. Session dùng
        # expire_on_commit=False, nên một đối tượng đã nằm trong identity map
        # sẽ được trả về nguyên trạng và các quan hệ đã nạp KHÔNG được đọc lại.
        # Hậu quả: vừa giao việc xong, đọc lại vẫn thấy `assignee = None` —
        # ghi đúng xuống DB nhưng trả sai cho client. Test đã bắt được lỗi này.
        ).execution_options(populate_existing=True)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        params: PageParams,
        *,
        visible: ColumnElement[bool],
        status: list[TicketStatus] | None = None,
        priority: list[TicketPriority] | None = None,
        category_id: UUID | None = None,
        assignee_id: UUID | None = None,
        requester_id: UUID | None = None,
        unassigned: bool = False,
        q: str | None = None,
        sort_by: str = "createdAt",
        sort_order: str = "desc",
    ) -> tuple[list[Ticket], int]:
        stmt: Select = select(Ticket).where(visible)

        if status:
            stmt = stmt.where(Ticket.status.in_(status))
        if priority:
            stmt = stmt.where(Ticket.priority.in_(priority))
        if category_id is not None:
            stmt = stmt.where(Ticket.category_id == category_id)
        if assignee_id is not None:
            stmt = stmt.where(Ticket.assignee_id == assignee_id)
        if requester_id is not None:
            stmt = stmt.where(Ticket.requester_id == requester_id)
        if unassigned:
            stmt = stmt.where(Ticket.assignee_id.is_(None))
        if q and q.strip():
            stmt = stmt.where(SEARCH_CONDITION).params(q=q.strip())

        total = self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        column = SORTABLE.get(sort_by, Ticket.created_at)
        ordering = column.desc() if sort_order == "desc" else column.asc()

        rows = self.session.execute(
            self._with_relations(stmt)
            .order_by(ordering, Ticket.id.desc())   # id để thứ tự ổn định khi trùng khoá sắp xếp
            .offset(params.offset)
            .limit(params.limit)
        ).scalars().all()

        return list(rows), total

    def queue_stats(self, agent_id: UUID, now: datetime) -> dict[str, int]:
        """Số đếm cho thanh bên của Agent (US-12) — MỘT truy vấn, không phải năm.

        Năm truy vấn riêng lẻ cho một thanh bên hiển thị trên mọi trang là
        cách chắc chắn nhất để dashboard trở thành điểm nghẽn.
        """
        mine_open = (Ticket.assignee_id == agent_id, Ticket.status.in_(OPEN_STATUSES))
        has_due = Ticket.sla_resolution_due_at.is_not(None)

        # Cùng ngưỡng với SlaCalculator.state(): còn <= 25% thời gian thì cảnh
        # báo. Nếu SQL và Python dùng hai định nghĩa khác nhau, con số trên
        # thanh bên sẽ không khớp với nhãn hiển thị trên từng ticket.
        remaining = func.extract("epoch", Ticket.sla_resolution_due_at - now)
        total = func.extract("epoch", Ticket.sla_resolution_due_at - Ticket.created_at)

        row = self.session.execute(
            select(
                func.count().filter(
                    Ticket.assignee_id.is_(None), Ticket.status == TicketStatus.NEW
                ).label("unassigned"),
                func.count().filter(*mine_open).label("assigned_to_me"),
                func.count().filter(
                    Ticket.assignee_id == agent_id,
                    Ticket.status == TicketStatus.IN_PROGRESS,
                ).label("in_progress"),
                func.count().filter(
                    *mine_open, has_due,
                    Ticket.sla_resolution_due_at > now,
                    total > 0,
                    remaining <= AT_RISK_RATIO * total,
                ).label("at_risk"),
                func.count().filter(
                    *mine_open, has_due, Ticket.sla_resolution_due_at <= now
                ).label("breached"),
            ).select_from(Ticket)
        ).mappings().one()
        return {k: int(v) for k, v in row.items()}


class CommentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, comment: TicketComment) -> TicketComment:
        self.session.add(comment)
        self.session.flush()
        return comment

    def list_for_ticket(
        self, ticket_id: UUID, *, include_internal: bool
    ) -> list[TicketComment]:
        """Lọc bình luận nội bộ NGAY TRONG SQL.

        Lấy hết rồi lọc trong Python là cách rò rỉ kinh điển: chỉ cần một
        endpoint quên gọi bộ lọc là nhân viên đọc được trao đổi nội bộ của IT.
        """
        stmt = (
            select(TicketComment)
            .options(selectinload(TicketComment.author))
            .where(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
        )
        if not include_internal:
            stmt = stmt.where(TicketComment.is_internal.is_(False))
        return list(self.session.execute(stmt).scalars().all())

    def count_agent_replies(self, ticket_id: UUID, requester_id: UUID) -> int:
        return self.session.execute(
            select(func.count())
            .select_from(TicketComment)
            .where(
                TicketComment.ticket_id == ticket_id,
                TicketComment.author_id != requester_id,
            )
        ).scalar_one()


class TicketEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: TicketEvent) -> TicketEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def list_for_ticket(self, ticket_id: UUID) -> list[TicketEvent]:
        stmt = (
            select(TicketEvent)
            .options(selectinload(TicketEvent.actor))
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
