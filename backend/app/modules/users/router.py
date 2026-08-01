"""Endpoint người dùng: hồ sơ cá nhân và quản trị (US-07).

★ Nhóm quản trị dùng `Depends(require_admin)` NGAY TRÊN ROUTE, không chỉ dựa
vào kiểm tra trong service. Hai lớp trùng nhau là chủ ý (tài liệu 08 §2.1):
nhìn vào chữ ký hàm là biết ngay ai gọi được, không phải lần theo service.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.modules.users.constants import UserRole
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    DepartmentBrief,
    UpdateProfileRequest,
    UserResponse,
)
from app.modules.users.service import UserService

router = APIRouter()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


# ── Hồ sơ cá nhân ─────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse, summary="Thông tin người đang đăng nhập")
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse, summary="Cập nhật hồ sơ cá nhân")
def update_me(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> User:
    return service.update_profile(current_user, data)


# ── US-07: Quản trị người dùng (chỉ Admin) ────────────────────────────


@router.get(
    "/departments",
    response_model=list[DepartmentBrief],
    summary="Danh sách phòng ban (để chọn khi tạo/sửa người dùng)",
)
def list_departments(
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> list[DepartmentBrief]:
    return [DepartmentBrief.model_validate(d) for d in service.list_departments()]


@router.get("", response_model=Page[UserResponse], summary="Tìm kiếm người dùng")
def list_users(
    q: str | None = Query(default=None, max_length=150, description="Tìm theo tên hoặc email"),
    role: UserRole | None = Query(default=None),
    department_id: UUID | None = Query(default=None, alias="departmentId"),
    is_active: bool | None = Query(default=None, alias="isActive"),
    sort_by: str = Query(default="createdAt", alias="sortBy"),
    sort_dir: str = Query(default="desc", alias="sortDir", pattern="^(asc|desc)$"),
    params: PageParams = Depends(page_params),
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> Page[UserResponse]:
    """`sortBy` chỉ nhận giá trị trong danh sách trắng `UserRepository.SORTABLE`;
    giá trị lạ rơi về `createdAt` thay vì báo lỗi — sắp xếp là tiện ích hiển
    thị, không đáng để làm hỏng cả màn hình."""
    items, total = service.list_users(
        params,
        q=q,
        role=role,
        department_id=department_id,
        is_active=is_active,
        sort_by=sort_by,
        sort_desc=(sort_dir == "desc"),
    )
    return Page.create([UserResponse.model_validate(u) for u in items], total, params)


@router.get("/agents", response_model=list[UserResponse], summary="IT Agent đang hoạt động")
def list_agents(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    """Dùng cho ô chọn người xử lý ở màn hình quản trị. Gợi ý có chấm điểm
    nằm ở `GET /tickets/{id}/assignee-suggestions` (US-20), không phải ở đây."""
    return [UserResponse.model_validate(u) for u in UserRepository(db).list_active_agents()]


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    summary="Tạo người dùng với vai trò bất kỳ",
)
def create_user(
    data: AdminCreateUserRequest,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> User:
    return service.create_user(current_user, data)


@router.get("/{user_id}", response_model=UserResponse, summary="Chi tiết một người dùng")
def get_user(
    user_id: UUID,
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> User:
    return service.get_user(user_id)


@router.patch("/{user_id}", response_model=UserResponse, summary="Sửa hồ sơ và vai trò")
def admin_update_user(
    user_id: UUID,
    data: AdminUpdateUserRequest,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> User:
    return service.admin_update(current_user, user_id, data)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Khoá tài khoản và thu hồi toàn bộ refresh token",
)
def deactivate_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> User:
    return service.set_active(current_user, user_id, is_active=False)


@router.post("/{user_id}/activate", response_model=UserResponse, summary="Mở khoá tài khoản")
def activate_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> User:
    return service.set_active(current_user, user_id, is_active=True)
