"""★ FILE MẪU — copy cấu trúc này khi viết schemas.py cho module khác.

Quy tắc:
- extra="forbid": field lạ bị TỪ CHỐI, không âm thầm bỏ qua
- Tách Input (client gửi) và Response (server trả) — không dùng chung một class
- Response dùng alias camelCase để khớp hợp đồng API (docs/design/06 §1)
- KHÔNG BAO GIỜ có field password/token trong Response
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.users.constants import UserRole


class StrictModel(BaseModel):
    """Base cho mọi schema đầu vào — từ chối field lạ."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Base cho mọi schema đầu ra — đọc được từ ORM, trả về camelCase."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ─────────────── Input ───────────────

class RegisterRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=150, alias="fullName")

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Mật khẩu phải có ít nhất 1 chữ hoa")
        if not any(c.islower() for c in v):
            raise ValueError("Mật khẩu phải có ít nhất 1 chữ thường")
        if not any(c.isdigit() for c in v):
            raise ValueError("Mật khẩu phải có ít nhất 1 chữ số")
        return v


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(alias="currentPassword", min_length=1)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=128)


# ─────────────── Output ───────────────

class UserBrief(ResponseModel):
    id: UUID
    email: str
    full_name: str = Field(serialization_alias="fullName")
    role: UserRole


class TokenResponse(ResponseModel):
    access_token: str = Field(serialization_alias="accessToken")
    token_type: str = Field(default="Bearer", serialization_alias="tokenType")
    expires_in: int = Field(serialization_alias="expiresIn")
    user: UserBrief
    # refresh_token KHÔNG nằm ở đây — nó được đặt trong cookie HttpOnly


class MeResponse(ResponseModel):
    id: UUID
    email: str
    full_name: str = Field(serialization_alias="fullName")
    role: UserRole
    department_id: UUID | None = Field(default=None, serialization_alias="departmentId")
    is_active: bool = Field(serialization_alias="isActive")
    created_at: datetime = Field(serialization_alias="createdAt")
