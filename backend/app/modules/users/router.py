"""Endpoint người dùng.

★ HIỆN CHỈ CÓ `/users/me` — phần Admin quản trị người dùng (US-07) và
`/users/agents` (US-20) CÒN TRỐNG, thuộc về người khác trong nhóm.
`/users/me` nằm ở đây vì frontend gọi nó ngay khi khởi động để khôi phục
phiên; thiếu nó thì không luồng nào chạy được.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.users.schemas import UpdateProfileRequest, UserResponse
from app.modules.users.service import UserService

router = APIRouter()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


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
