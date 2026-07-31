"""Lỗi nghiệp vụ.

QUY TẮC: tầng service KHÔNG BAO GIỜ ném HTTPException — chỉ ném DomainError.
Lý do: service phải dùng được cả trong Celery worker và CLI, nơi không có HTTP.
Việc dịch sang mã HTTP là của error_handlers.py.
"""

from typing import Any


class DomainError(Exception):
    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    default_message: str = "Đã có lỗi xảy ra"

    def __init__(
        self,
        message: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        # Một số lỗi cần kèm header theo chuẩn HTTP — ví dụ 429 phải có
        # `Retry-After` thì client mới biết chờ bao lâu. Service vẫn không
        # biết gì về HTTP: nó chỉ khai báo header, error_handlers gắn vào.
        self.headers = headers
        super().__init__(self.message)


class NotFoundError(DomainError):
    code, http_status, default_message = "NOT_FOUND", 404, "Không tìm thấy dữ liệu"


class ForbiddenError(DomainError):
    code, http_status, default_message = "FORBIDDEN", 403, "Bạn không có quyền thực hiện"


class UnauthenticatedError(DomainError):
    code, http_status, default_message = "UNAUTHENTICATED", 401, "Vui lòng đăng nhập"


class InvalidCredentialsError(DomainError):
    code, http_status = "INVALID_CREDENTIALS", 401
    default_message = "Email hoặc mật khẩu không đúng"


class AccountDisabledError(DomainError):
    code, http_status, default_message = "ACCOUNT_DISABLED", 403, "Tài khoản đã bị khoá"


class ValidationError(DomainError):
    code, http_status, default_message = "VALIDATION_ERROR", 422, "Dữ liệu không hợp lệ"


class ConflictError(DomainError):
    code, http_status, default_message = "CONFLICT", 409, "Dữ liệu bị xung đột"


class InvalidStatusTransitionError(DomainError):
    code, http_status = "INVALID_STATUS_TRANSITION", 422
    default_message = "Không thể chuyển sang trạng thái này"


class RateLimitError(DomainError):
    code, http_status = "RATE_LIMITED", 429
    default_message = "Bạn thao tác quá nhanh, vui lòng thử lại sau"


class ExternalServiceError(DomainError):
    code, http_status = "UPSTREAM_ERROR", 502
    default_message = "Dịch vụ bên ngoài tạm thời không phản hồi"


class BudgetExceededError(DomainError):
    code, http_status = "AI_BUDGET_EXCEEDED", 503
    default_message = "Tính năng AI tạm ngưng do đã đạt hạn mức tháng"
