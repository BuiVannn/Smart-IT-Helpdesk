"""TicketService — vòng đời ticket (US-08 → US-18).

Service này KHÔNG tự viết lại quy tắc: nó điều phối ba lớp thuần đã có sẵn.

    TicketStateMachine  — bước chuyển trạng thái nào hợp lệ, ai được làm
    TicketAccessPolicy  — ai nhìn thấy / sửa được ticket nào
    SlaCalculator       — hạn SLA theo giờ hành chính

Ba lớp đó không chạm database nên test được trong mili-giây và đã phủ hết
các nhánh. Nếu logic bị chép lại vào đây, hai bản sẽ trôi khác nhau và bản
trong service — bản thật sự chạy — là bản không ai test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.pagination import PageParams
from app.modules.tickets.constants import (
    ActorType,
    EventType,
    SlaState,
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from app.modules.tickets.models import (
    SlaPolicy,
    Ticket,
    TicketComment,
    TicketEvent,
)
from app.modules.tickets.policies import TicketAccessPolicy
from app.modules.tickets.repository import (
    CommentRepository,
    TicketEventRepository,
    TicketRepository,
)
from app.modules.tickets.schemas import (
    ChangeStatusRequest,
    CreateTicketRequest,
    UpdateTicketRequest,
)
from app.modules.tickets.sla import BusinessCalendar, SlaCalculator
from app.modules.tickets.state_machine import TicketStateMachine
from app.modules.users.constants import UserRole
from app.modules.users.models import Holiday, User

logger = get_logger(__name__)


class TicketService:
    def __init__(self, session: Session) -> None:
        self.db = session
        self.tickets = TicketRepository(session)
        self.comments = CommentRepository(session)
        self.events = TicketEventRepository(session)
        self._sla: SlaCalculator | None = None

    # ── US-08: Tạo ticket ─────────────────────────────────────────────

    def create(self, user: User, data: CreateTicketRequest) -> Ticket:
        priority = data.priority or self._default_priority(data.category_id)

        ticket = Ticket(
            code=self.tickets.next_code(),
            title=data.title.strip(),
            description=data.description.strip(),
            status=TicketStatus.NEW,
            priority=priority,
            requester_id=user.id,
            category_id=data.category_id,
            department_id=user.department_id,
            source=TicketSource.CHATBOT if data.chat_session_id else TicketSource.WEB,
            chat_session_id=data.chat_session_id,
        )
        self._apply_sla(ticket)
        self.tickets.add(ticket)

        self._record(ticket, user, EventType.CREATED, new_value=ticket.code)
        self.db.commit()

        # ★ ĐIỂM MÓC CHO AI PHÂN LOẠI (US-19) — người làm F3 chỉ cần thêm:
        #     from app.modules.tickets.tasks import classify_ticket
        #     classify_ticket.delay(str(ticket.id))
        # Gọi BẤT ĐỒNG BỘ và chỉ sau khi commit. Gọi đồng bộ thì mỗi lần tạo
        # ticket phải chờ LLM 5–20 giây, và LLM hỏng là không tạo được ticket.
        logger.info("tạo ticket", extra={"extra_fields": {
            "ticket_id": str(ticket.id), "code": ticket.code, "priority": priority
        }})
        return self._load(user, ticket.id)

    # ── US-10, US-12, US-16: Danh sách, hàng chờ, tìm kiếm ────────────

    def list(
        self,
        user: User,
        params: PageParams,
        *,
        status: list[TicketStatus] | None = None,
        priority: list[TicketPriority] | None = None,
        category_id: UUID | None = None,
        assignee_id: UUID | None = None,
        mine: bool = False,
        unassigned: bool = False,
        q: str | None = None,
        sort_by: str = "createdAt",
        sort_order: str = "desc",
    ) -> tuple[list[Ticket], int]:
        return self.tickets.list(
            params,
            visible=TicketAccessPolicy.visible_filter(user),
            status=status,
            priority=priority,
            category_id=category_id,
            assignee_id=user.id if mine else assignee_id,
            unassigned=unassigned,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def queue_stats(self, user: User) -> dict[str, int]:
        if not TicketAccessPolicy.can_assign(user):
            raise ForbiddenError("Chỉ IT Agent và Admin xem được hàng chờ")
        return self.tickets.queue_stats(user.id, datetime.now(UTC))

    # ── US-11: Chi tiết ───────────────────────────────────────────────

    def get(self, user: User, ticket_id: UUID) -> Ticket:
        return self._load(user, ticket_id)

    def allowed_transitions(self, user: User, ticket_id: UUID) -> list[TicketStatus]:
        ticket = self._load(user, ticket_id)
        return TicketStateMachine.allowed_next(ticket.status, user.role)

    # ── Sửa nội dung ──────────────────────────────────────────────────

    def update(self, user: User, ticket_id: UUID, data: UpdateTicketRequest) -> Ticket:
        ticket = self._load(user, ticket_id)
        self._check_version(ticket, data.version)

        if not TicketAccessPolicy.can_edit(user, ticket):
            raise ForbiddenError(
                "Chỉ sửa được ticket của mình khi còn ở trạng thái NEW"
            )

        changed = False
        if data.title is not None and data.title.strip() != ticket.title:
            ticket.title = data.title.strip()
            changed = True
        if data.description is not None and data.description.strip() != ticket.description:
            ticket.description = data.description.strip()
            changed = True
        if data.category_id is not None and data.category_id != ticket.category_id:
            self._record(
                ticket, user, EventType.RECLASSIFIED,
                field_name="category_id",
                old_value=str(ticket.category_id or ""),
                new_value=str(data.category_id),
            )
            ticket.category_id = data.category_id
            changed = True
        if data.priority is not None and data.priority != ticket.priority:
            self._record(
                ticket, user, EventType.PRIORITY_CHANGED,
                field_name="priority",
                old_value=ticket.priority, new_value=data.priority,
            )
            ticket.priority = data.priority
            # Hạn SLA được tính lại theo mức ưu tiên MỚI, nhưng vẫn tính từ
            # thời điểm TẠO ticket — không phải từ bây giờ. Tính lại từ bây giờ
            # là tự gia hạn cho mình mỗi lần đổi mức ưu tiên.
            self._apply_sla(ticket)
            changed = True

        if changed:
            self._bump(ticket)
            self.db.commit()
        return self._load(user, ticket_id)

    # ── US-13: Nhận việc / giao việc ──────────────────────────────────

    def claim(self, user: User, ticket_id: UUID, version: int) -> Ticket:
        """IT Agent tự nhận ticket chưa có người xử lý."""
        if not TicketAccessPolicy.can_claim(user):
            raise ForbiddenError("Chỉ IT Agent mới tự nhận ticket")

        ticket = self._load(user, ticket_id)
        self._check_version(ticket, version)

        if ticket.assignee_id is not None:
            # Đây chính là tình huống optimistic lock bảo vệ: hai Agent cùng
            # bấm "Nhận việc". Người thứ hai phải biết mình thua, chứ không
            # được âm thầm ghi đè người thứ nhất.
            raise ConflictError(
                "Ticket đã có người nhận",
                details={"assigneeId": str(ticket.assignee_id)},
            )

        return self._do_assign(user, ticket, user.id)

    def assign(self, user: User, ticket_id: UUID, assignee_id: UUID, version: int) -> Ticket:
        if not TicketAccessPolicy.can_assign(user):
            raise ForbiddenError("Bạn không có quyền giao việc")

        ticket = self._load(user, ticket_id)
        self._check_version(ticket, version)

        assignee = self.db.get(User, assignee_id)
        if assignee is None:
            raise NotFoundError("Không tìm thấy người được giao")
        # BR-02: chỉ IT Agent đang hoạt động mới nhận việc được. Giao cho một
        # nhân viên thường nghĩa là ticket rơi vào hố đen.
        if not assignee.can_be_assigned:
            raise ValidationError(
                "Chỉ giao được cho IT Agent đang hoạt động",
                details={"assigneeId": str(assignee_id)},
            )

        return self._do_assign(user, ticket, assignee_id)

    def _do_assign(self, user: User, ticket: Ticket, assignee_id: UUID) -> Ticket:
        # Dùng get_rule chứ không dùng validate(): giao lại một ticket đang ở
        # ASSIGNED là bước chuyển ASSIGNED → ASSIGNED, mà validate() từ chối
        # thẳng mọi trường hợp from == to. Bảng ALLOWED mới là nguồn sự thật,
        # và nó CÓ khai báo bước tự chuyển này (dòng "giao lại").
        rule = TicketStateMachine.get_rule(ticket.status, TicketStatus.ASSIGNED, user.role)
        if rule is None:
            raise InvalidStatusTransitionError(
                f"Không giao việc được khi ticket đang ở trạng thái {ticket.status}",
                details={
                    "currentStatus": ticket.status,
                    "allowedStatuses": TicketStateMachine.allowed_next(
                        ticket.status, user.role
                    ),
                },
            )

        old_assignee = ticket.assignee_id
        old_status = ticket.status
        ticket.assignee_id = assignee_id
        ticket.status = TicketStatus.ASSIGNED

        if old_status != ticket.status:
            self._record(
                ticket, user, EventType.STATUS_CHANGED,
                field_name="status", old_value=old_status, new_value=ticket.status,
            )

        self._record(
            ticket, user, EventType.ASSIGNED,
            field_name="assignee_id",
            old_value=str(old_assignee) if old_assignee else None,
            new_value=str(assignee_id),
        )
        self._bump(ticket)
        self.db.commit()
        return self._load(user, ticket.id)

    # ── US-14, US-18: Chuyển trạng thái / đóng / huỷ ──────────────────

    def change_status(
        self, user: User, ticket_id: UUID, data: ChangeStatusRequest
    ) -> Ticket:
        ticket = self._load(user, ticket_id)
        self._check_version(ticket, data.version)

        old_status = ticket.status
        TicketStateMachine.validate(
            from_status=old_status,
            to_status=data.status,
            role=user.role,
            is_requester=ticket.requester_id == user.id,
            is_assignee=ticket.assignee_id == user.id,
            has_assignee=ticket.assignee_id is not None,
            resolution_note=data.resolution_note or ticket.resolution_note,
        )

        if old_status == TicketStatus.RESOLVED and data.status == TicketStatus.IN_PROGRESS:
            self._check_reopen_window(ticket)

        now = datetime.now(UTC)
        ticket.status = data.status

        if data.resolution_note:
            ticket.resolution_note = data.resolution_note.strip()

        if data.status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
        elif data.status == TicketStatus.CLOSED:
            ticket.closed_at = now
            # RESOLVED → CLOSED có thể do người dùng bấm ngay; nếu chưa từng
            # qua RESOLVED thì resolved_at vẫn phải có, do CHECK constraint.
            ticket.resolved_at = ticket.resolved_at or now
        elif old_status == TicketStatus.RESOLVED:
            # Mở lại: xoá dấu đã xử lý, nếu không báo cáo "thời gian xử lý
            # trung bình" (US-38) sẽ đếm ticket này là đã xong.
            ticket.resolved_at = None
            self._record(ticket, user, EventType.REOPENED)

        self._mark_first_response(ticket, user, now)

        self._record(
            ticket, user, EventType.STATUS_CHANGED,
            field_name="status", old_value=old_status, new_value=data.status,
        )
        self._bump(ticket)
        self.db.commit()

        logger.info("đổi trạng thái ticket", extra={"extra_fields": {
            "ticket_id": str(ticket.id), "from": old_status, "to": data.status
        }})
        return self._load(user, ticket_id)

    # ── US-15: Bình luận ──────────────────────────────────────────────

    def add_comment(
        self, user: User, ticket_id: UUID, body: str, is_internal: bool
    ) -> TicketComment:
        ticket = self._load(user, ticket_id)

        if not TicketAccessPolicy.can_comment(user, ticket):
            raise ForbiddenError("Bạn không có quyền bình luận trên ticket này")

        # Employee gửi is_internal=true thì BỎ QUA, không báo lỗi (BR-10).
        # Báo lỗi là tự khai rằng có tồn tại loại bình luận nội bộ.
        internal = is_internal and TicketAccessPolicy.can_use_internal_comment(user)

        comment = self.comments.add(
            TicketComment(
                ticket_id=ticket.id,
                author_id=user.id,
                body=body.strip(),
                is_internal=internal,
            )
        )

        # Bình luận nội bộ KHÔNG tính là đã phản hồi người dùng — người dùng
        # không nhìn thấy nó, tính vào là làm đẹp số liệu SLA một cách sai sự thật.
        if not internal:
            self._mark_first_response(ticket, user, datetime.now(UTC))

        self._record(
            ticket, user, EventType.COMMENTED,
            event_metadata={"commentId": str(comment.id), "isInternal": internal},
        )
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def list_comments(self, user: User, ticket_id: UUID) -> list[TicketComment]:
        self._load(user, ticket_id)   # kiểm tra quyền xem ticket trước
        return self.comments.list_for_ticket(
            ticket_id,
            include_internal=TicketAccessPolicy.can_see_internal_comments(user),
        )

    # ── US-17: Lịch sử thay đổi ───────────────────────────────────────

    def list_events(self, user: User, ticket_id: UUID) -> list[TicketEvent]:
        self._load(user, ticket_id)
        return self.events.list_for_ticket(ticket_id)

    # ── Nội bộ ────────────────────────────────────────────────────────

    def _load(self, user: User, ticket_id: UUID) -> Ticket:
        """Đọc ticket qua bộ lọc quyền.

        ★ Trả 404 chứ KHÔNG phải 403 khi ticket thuộc người khác. 403 là tự
        xác nhận "ticket này có tồn tại", cho phép dò mã ticket của công ty.
        """
        ticket = self.tickets.get(ticket_id, TicketAccessPolicy.visible_filter(user))
        if ticket is None:
            raise NotFoundError("Không tìm thấy ticket")
        return ticket

    def _check_version(self, ticket: Ticket, version: int) -> None:
        """Khoá lạc quan (BR-16).

        Không có bước này thì hai Agent mở cùng một ticket, người sau bấm lưu
        sẽ ghi đè im lặng lên thay đổi của người trước — và không ai biết.
        """
        if ticket.version != version:
            raise ConflictError(
                "Ticket đã được người khác cập nhật. Vui lòng tải lại.",
                details={"currentVersion": ticket.version},
            )

    @staticmethod
    def _bump(ticket: Ticket) -> None:
        ticket.version += 1

    def _mark_first_response(self, ticket: Ticket, user: User, now: datetime) -> None:
        """Ghi nhận lần phản hồi đầu tiên của IT — mốc đo SLA phản hồi.

        Chỉ tính khi người thao tác KHÔNG phải người tạo ticket: người tạo tự
        bình luận thêm không phải là IT đã phản hồi.
        """
        if (
            ticket.first_response_at is None
            and user.id != ticket.requester_id
            and user.role in (UserRole.IT_AGENT, UserRole.ADMIN)
        ):
            ticket.first_response_at = now

    def _check_reopen_window(self, ticket: Ticket) -> None:
        if ticket.resolved_at is None:
            return
        days = (datetime.now(UTC) - ticket.resolved_at).days
        if days > TicketStateMachine.REOPEN_WINDOW_DAYS:
            raise ValidationError(
                f"Chỉ mở lại được trong {TicketStateMachine.REOPEN_WINDOW_DAYS} "
                f"ngày kể từ khi xử lý xong. Vui lòng tạo ticket mới."
            )

    def _record(
        self,
        ticket: Ticket,
        user: User | None,
        event_type: EventType,
        *,
        field_name: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        event_metadata: dict | None = None,
    ) -> None:
        """Ghi vào nhật ký chỉ-ghi-thêm (BR-17)."""
        self.events.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=user.id if user else None,
                actor_type=ActorType.USER if user else ActorType.SYSTEM,
                event_type=event_type,
                field_name=field_name,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                event_metadata=event_metadata or {},
            )
        )

    def _default_priority(self, category_id: UUID | None) -> TicketPriority:
        """Mức ưu tiên mặc định lấy từ loại sự cố, không phải hằng số cứng."""
        if category_id is None:
            return TicketPriority.MEDIUM
        from app.modules.tickets.models import TicketCategory

        category = self.db.get(TicketCategory, category_id)
        return category.default_priority if category else TicketPriority.MEDIUM

    def _apply_sla(self, ticket: Ticket) -> None:
        """SAO CHÉP hạn SLA vào ticket (BR-19).

        Không tính lại từ policy mỗi lần đọc: đổi chính sách SLA về sau sẽ làm
        thay đổi hạn của ticket cũ, và báo cáo lịch sử trở thành vô nghĩa.
        """
        policy = self.db.execute(
            select(SlaPolicy).where(SlaPolicy.priority == ticket.priority)
        ).scalar_one_or_none()
        if policy is None:
            logger.warning(f"chưa cấu hình SLA cho mức ưu tiên {ticket.priority}")
            return

        start = ticket.created_at or datetime.now(UTC)
        calculator = self._sla_calculator()
        ticket.sla_response_due_at = calculator.due_at(
            start, policy.first_response_minutes, policy.business_hours_only
        )
        ticket.sla_resolution_due_at = calculator.due_at(
            start, policy.resolution_minutes, policy.business_hours_only
        )

    def _sla_calculator(self) -> SlaCalculator:
        """Nạp ngày nghỉ MỘT lần cho mỗi request, không phải mỗi ticket."""
        if self._sla is None:
            holidays = frozenset(
                row.holiday_date.date()
                for row in self.db.execute(select(Holiday)).scalars().all()
            )
            self._sla = SlaCalculator(BusinessCalendar(holidays=holidays))
        return self._sla

    def sla_state(self, ticket: Ticket, now: datetime | None = None) -> SlaState:
        return self._sla_calculator().state(
            created_at=ticket.created_at,
            due_at=ticket.sla_resolution_due_at,
            resolved_at=ticket.resolved_at,
            now=now or datetime.now(UTC),
            paused_seconds=ticket.paused_seconds,
        )
