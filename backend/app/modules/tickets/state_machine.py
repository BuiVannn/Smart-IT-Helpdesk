"""Máy trạng thái ticket — LỚP THUẦN, không I/O.

★ Đây là một trong ba lớp dễ sai nhất của hệ thống. Nó KHÔNG nhận Session,
KHÔNG gọi mạng, KHÔNG đọc file. Nhờ vậy unit test chạy trong mili-giây và
phủ được toàn bộ 49 ô của bảng chuyển trạng thái mà không cần database.

Bảng ALLOWED dưới đây là NGUỒN SỰ THẬT DUY NHẤT, khớp với docs/design/03 §5.
Sửa ở đây thì phải sửa tài liệu, và ngược lại.
"""

from dataclasses import dataclass

from app.core.exceptions import InvalidStatusTransitionError
from app.modules.tickets.constants import TicketStatus
from app.modules.users.constants import UserRole

S = TicketStatus
R = UserRole


@dataclass(frozen=True)
class TransitionRule:
    """Một bước chuyển hợp lệ: từ trạng thái nào, sang trạng thái nào, ai được làm."""

    to_status: TicketStatus
    allowed_roles: frozenset[UserRole]
    requires_assignee: bool = False
    requires_resolution_note: bool = False
    requester_only: bool = False  # chỉ người TẠO ticket được thực hiện
    assignee_only: bool = False  # chỉ người ĐƯỢC GIAO được thực hiện


ALL_ROLES = frozenset({R.EMPLOYEE, R.IT_AGENT, R.ADMIN})
AGENT_ADMIN = frozenset({R.IT_AGENT, R.ADMIN})
ADMIN_ONLY = frozenset({R.ADMIN})


class TicketStateMachine:
    """Kiểm tra và liệt kê các bước chuyển trạng thái hợp lệ."""

    ALLOWED: dict[TicketStatus, tuple[TransitionRule, ...]] = {
        S.NEW: (
            TransitionRule(S.ASSIGNED, AGENT_ADMIN, requires_assignee=True),
            TransitionRule(S.CANCELLED, frozenset({R.EMPLOYEE, R.ADMIN}), requester_only=True),
        ),
        S.ASSIGNED: (
            TransitionRule(S.ASSIGNED, AGENT_ADMIN, requires_assignee=True),  # giao lại
            TransitionRule(S.IN_PROGRESS, AGENT_ADMIN, assignee_only=True),
            TransitionRule(S.CANCELLED, frozenset({R.EMPLOYEE, R.ADMIN}), requester_only=True),
        ),
        S.IN_PROGRESS: (
            TransitionRule(S.ASSIGNED, ADMIN_ONLY, requires_assignee=True),  # giao lại
            TransitionRule(S.PENDING_REQUESTER, AGENT_ADMIN, assignee_only=True),
            TransitionRule(
                S.RESOLVED, AGENT_ADMIN, assignee_only=True, requires_resolution_note=True
            ),
            TransitionRule(S.CANCELLED, ADMIN_ONLY),
        ),
        S.PENDING_REQUESTER: (
            TransitionRule(S.IN_PROGRESS, ALL_ROLES),
            TransitionRule(
                S.RESOLVED, AGENT_ADMIN, assignee_only=True, requires_resolution_note=True
            ),
            TransitionRule(S.CANCELLED, ADMIN_ONLY),
        ),
        S.RESOLVED: (
            # Mở lại — trong 7 ngày, xem REOPEN_WINDOW_DAYS
            TransitionRule(S.IN_PROGRESS, frozenset({R.EMPLOYEE, R.ADMIN}), requester_only=True),
            TransitionRule(S.CLOSED, ALL_ROLES),
        ),
        S.CLOSED: (),  # trạng thái cuối
        S.CANCELLED: (),  # trạng thái cuối
    }

    REOPEN_WINDOW_DAYS = 7
    AUTO_CLOSE_AFTER_DAYS = 3
    MIN_RESOLUTION_NOTE_LENGTH = 10

    @classmethod
    def can_transition(
        cls, from_status: TicketStatus, to_status: TicketStatus, role: UserRole
    ) -> bool:
        """Kiểm tra nhanh, không xét ngữ cảnh ticket cụ thể."""
        return any(
            rule.to_status == to_status and role in rule.allowed_roles
            for rule in cls.ALLOWED.get(from_status, ())
        )

    @classmethod
    def get_rule(
        cls, from_status: TicketStatus, to_status: TicketStatus, role: UserRole
    ) -> TransitionRule | None:
        for rule in cls.ALLOWED.get(from_status, ()):
            if rule.to_status == to_status and role in rule.allowed_roles:
                return rule
        return None

    @classmethod
    def allowed_next(cls, from_status: TicketStatus, role: UserRole) -> list[TicketStatus]:
        """Các trạng thái kế tiếp hợp lệ cho vai trò này.

        Frontend gọi GET /tickets/{id}/allowed-transitions để CHỈ HIỂN THỊ
        nút hợp lệ, thay vì hiện hết rồi báo lỗi. Máy trạng thái vẫn nằm ở
        backend — frontend chỉ hỏi.
        """
        return [
            rule.to_status
            for rule in cls.ALLOWED.get(from_status, ())
            if role in rule.allowed_roles and rule.to_status != from_status
        ]

    @classmethod
    def validate(
        cls,
        *,
        from_status: TicketStatus,
        to_status: TicketStatus,
        role: UserRole,
        is_requester: bool = False,
        is_assignee: bool = False,
        has_assignee: bool = False,
        resolution_note: str | None = None,
    ) -> None:
        """Ném InvalidStatusTransitionError nếu bước chuyển không hợp lệ.

        Thông điệp lỗi LUÔN kèm danh sách trạng thái được phép, để frontend
        hiển thị được hướng dẫn cụ thể thay vì chỉ báo "không hợp lệ".
        """
        if from_status == to_status:
            raise InvalidStatusTransitionError(
                f"Ticket đã ở trạng thái {to_status}",
                details={"currentStatus": from_status, "allowedStatuses": []},
            )

        rule = cls.get_rule(from_status, to_status, role)
        if rule is None:
            raise InvalidStatusTransitionError(
                f"Không thể chuyển từ {from_status} sang {to_status}",
                details={
                    "currentStatus": from_status,
                    "allowedStatuses": cls.allowed_next(from_status, role),
                },
            )

        if rule.requester_only and not is_requester and role != R.ADMIN:
            raise InvalidStatusTransitionError("Chỉ người tạo ticket mới thực hiện được")

        if rule.assignee_only and not is_assignee and role != R.ADMIN:
            raise InvalidStatusTransitionError("Chỉ người được giao xử lý mới thực hiện được")

        if rule.requires_assignee and not has_assignee:
            raise InvalidStatusTransitionError("Phải chỉ định người xử lý trước")

        if rule.requires_resolution_note:
            note = (resolution_note or "").strip()
            if len(note) < cls.MIN_RESOLUTION_NOTE_LENGTH:
                raise InvalidStatusTransitionError(
                    f"Phải nhập ghi chú xử lý ít nhất " f"{cls.MIN_RESOLUTION_NOTE_LENGTH} ký tự"
                )
