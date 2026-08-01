"""Chính sách truy cập ticket — LỚP THUẦN, không I/O.

★ Đây là chỗ rủi ro NGHIÊM TRỌNG NHẤT của hệ thống: nhân viên đọc được
ticket của người khác. Tách riêng khỏi service để quy tắc nằm ở MỘT CHỖ
duy nhất và liệt kê hết được bằng test.

Nguyên tắc: LỌC NGAY TRONG TRUY VẤN, không lấy hết rồi lọc bằng Python.
Lấy hết rồi lọc sau sẽ khiến totalItems trong phân trang sai, làm lộ số
lượng ticket của toàn hệ thống, và chỉ cần một chỗ quên lọc là rò rỉ dữ liệu.
"""

from sqlalchemy import ColumnElement, true

from app.modules.tickets.constants import TicketStatus
from app.modules.tickets.models import Ticket
from app.modules.users.constants import UserRole


class TicketAccessPolicy:
    @staticmethod
    def visible_filter(user) -> ColumnElement[bool]:
        """Điều kiện WHERE quyết định người dùng được NHÌN THẤY ticket nào.

        Repository BẮT BUỘC nhận điều kiện này — không có đường nào truy vấn
        ticket mà bỏ qua nó.
        """
        if user.role in (UserRole.IT_AGENT, UserRole.ADMIN):
            return true()
        return Ticket.requester_id == user.id

    @staticmethod
    def can_view(user, ticket) -> bool:
        if user.role in (UserRole.IT_AGENT, UserRole.ADMIN):
            return True
        return ticket.requester_id == user.id

    @staticmethod
    def can_comment(user, ticket) -> bool:
        if user.role in (UserRole.IT_AGENT, UserRole.ADMIN):
            return True
        return ticket.requester_id == user.id

    @staticmethod
    def can_use_internal_comment(user) -> bool:
        """Employee gửi is_internal=true thì bị BỎ QUA, không báo lỗi."""
        return user.role in (UserRole.IT_AGENT, UserRole.ADMIN)

    @staticmethod
    def can_see_internal_comments(user) -> bool:
        return user.role in (UserRole.IT_AGENT, UserRole.ADMIN)

    @staticmethod
    def can_assign(user) -> bool:
        return user.role in (UserRole.IT_AGENT, UserRole.ADMIN)

    @staticmethod
    def can_claim(user) -> bool:
        """Chỉ IT Agent tự nhận ticket. Admin giao chứ không nhận."""
        return user.role == UserRole.IT_AGENT

    @staticmethod
    def can_edit(user, ticket) -> bool:
        if user.role == UserRole.ADMIN:
            return True
        if user.role == UserRole.IT_AGENT:
            return True
        # Employee chỉ sửa được ticket của mình khi còn ở trạng thái NEW
        return ticket.requester_id == user.id and ticket.status == TicketStatus.NEW

    @staticmethod
    def can_rate(user, ticket) -> bool:
        """Chỉ người tạo ticket được đánh giá, và chỉ khi đã xử lý xong (BR-07)."""
        return ticket.requester_id == user.id and ticket.status in (
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
        )
