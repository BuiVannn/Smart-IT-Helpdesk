"""★ FILE MẪU — copy cấu trúc này khi viết schemas.py cho module khác.

Quy tắc:
- Kế thừa StrictModel (đầu vào) / ResponseModel (đầu ra) từ `app.core.schemas`
- Tách Input (client gửi) và Response (server trả) — không dùng chung một class
- Response dùng alias camelCase để khớp hợp đồng API (docs/design/06 §1)
- KHÔNG BAO GIỜ có field password/token trong Response

Biểu diễn người dùng lấy từ `app.modules.users.schemas` — auth chỉ lo token.
Nếu auth tự định nghĩa lại hình dạng user, hai bên sẽ trôi khác nhau và
frontend phải xử lý hai kiểu dữ liệu cho cùng một thứ.
"""

from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field

from app.core.schemas import ResponseModel, StrictModel
from app.modules.users.schemas import UserResponse


def _check_password_policy(v: str) -> str:
    if not any(c.isupper() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ hoa")
    if not any(c.islower() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ thường")
    if not any(c.isdigit() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số")
    return v


# Chính sách mật khẩu khai báo MỘT chỗ rồi dùng lại — đăng ký và đổi mật khẩu
# mà kiểm tra khác nhau là cách kinh điển để lọt mật khẩu yếu qua đường vòng.
Password = Annotated[
    str, Field(min_length=8, max_length=128), AfterValidator(_check_password_policy)
]


# ─────────────── Input ───────────────


class RegisterRequest(StrictModel):
    email: EmailStr
    password: Password
    full_name: str = Field(min_length=2, max_length=150, alias="fullName")


class LoginRequest(StrictModel):
    email: EmailStr
    # KHÔNG áp chính sách mật khẩu ở đây: đăng nhập chỉ so khớp. Nếu bắt lỗi
    # định dạng thì hệ thống vô tình tiết lộ mật khẩu cũ không đạt chuẩn mới.
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(alias="currentPassword", min_length=1)
    new_password: Password = Field(alias="newPassword")


# ─────────────── Output ───────────────


class TokenResponse(ResponseModel):
    access_token: str = Field(serialization_alias="accessToken")
    token_type: str = Field(default="Bearer", serialization_alias="tokenType")
    expires_in: int = Field(serialization_alias="expiresIn")
    user: UserResponse
    # refresh_token KHÔNG nằm ở đây — nó nằm trong cookie HttpOnly.
    # Để trong body thì JavaScript đọc được, và một lỗ hổng XSS bất kỳ là mất
    # phiên 7 ngày của người dùng.
