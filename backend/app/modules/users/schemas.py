"""Schema của module users.

Biểu diễn "người dùng" nằm ở ĐÂY, không nằm ở auth. Auth chỉ lo token; nếu
mỗi module tự định nghĩa hình dạng user riêng thì chúng sẽ trôi khác nhau và
frontend phải xử lý hai kiểu dữ liệu cho cùng một thứ.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel, StrictModel
from app.modules.users.constants import UserRole


class DepartmentBrief(ResponseModel):
    id: UUID
    code: str
    name: str


class UserBrief(ResponseModel):
    """Dùng khi user xuất hiện lồng trong tài nguyên khác (người tạo ticket,
    người bình luận...). Cố tình KHÔNG có email — danh sách ticket không phải
    chỗ để lộ email toàn công ty."""

    id: UUID
    full_name: str = Field(serialization_alias="fullName")
    role: UserRole
    avatar_url: str | None = Field(default=None, serialization_alias="avatarUrl")


class UserResponse(ResponseModel):
    """Thông tin đầy đủ — chỉ trả cho chính chủ hoặc cho Admin."""

    id: UUID
    email: str
    full_name: str = Field(serialization_alias="fullName")
    role: UserRole
    department: DepartmentBrief | None = None
    phone: str | None = None
    avatar_url: str | None = Field(default=None, serialization_alias="avatarUrl")
    is_active: bool = Field(serialization_alias="isActive")
    last_login_at: datetime | None = Field(default=None, serialization_alias="lastLoginAt")
    created_at: datetime = Field(serialization_alias="createdAt")


class UpdateProfileRequest(StrictModel):
    """Người dùng tự sửa hồ sơ.

    Cố tình KHÔNG có `role`, `isActive`, `email`: nâng quyền cho chính mình
    phải là việc bất khả thi ở tầng schema, chứ không phải một câu `if` mà ai
    đó có thể quên viết trong service.
    """

    full_name: str | None = Field(default=None, alias="fullName", min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = Field(default=None, alias="avatarUrl", max_length=500)
