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

from pydantic import EmailStr, Field

from app.core.schemas import ResponseModel, StrictModel

# `Password` (chính sách mật khẩu) đã chuyển sang `app/core/security.py` để
# module `users` dùng chung được — US-07 cho phép Admin tạo tài khoản hộ, và
# mật khẩu khởi tạo đó phải chịu đúng một chính sách với mật khẩu tự đăng ký.
from app.core.security import Password
from app.modules.users.schemas import UserResponse

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
