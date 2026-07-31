"""Dependency dùng chung: lấy user hiện tại, kiểm tra vai trò.

★ MỌI endpoint nghiệp vụ PHẢI có một trong các dependency này. Có một test
tự động quét toàn bộ route để bảo đảm không endpoint nào bị bỏ sót
(xem tests/api/test_permission_matrix.py).
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AccountDisabledError, ForbiddenError, UnauthenticatedError
from app.core.logging import user_id_ctx
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.users.constants import UserRole
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthenticatedError("Thiếu token xác thực")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise UnauthenticatedError("Token không hợp lệ")

    user = UserRepository(db).get_by_id(UUID(subject))
    if user is None:
        raise UnauthenticatedError("Tài khoản không tồn tại")
    if not user.is_active:
        raise AccountDisabledError()

    user_id_ctx.set(str(user.id))   # để mọi dòng log trong request có user_id
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dùng: current_user: User = Depends(require_role(UserRole.ADMIN))"""

    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("Bạn không có quyền thực hiện thao tác này")
        return user

    return _guard


require_admin = require_role(UserRole.ADMIN)
require_agent = require_role(UserRole.IT_AGENT, UserRole.ADMIN)
require_any_role = require_role(UserRole.EMPLOYEE, UserRole.IT_AGENT, UserRole.ADMIN)
