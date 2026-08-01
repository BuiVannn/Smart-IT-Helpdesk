"""UserService — hồ sơ cá nhân và quản trị người dùng (US-07)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.pagination import PageParams
from app.core.security import hash_password
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.users.constants import UserRole
from app.modules.users.models import Department, User
from app.modules.users.repository import DepartmentRepository, UserRepository
from app.modules.users.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    UpdateProfileRequest,
)

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: Session) -> None:
        self.db = session
        self.users = UserRepository(session)
        self.departments = DepartmentRepository(session)
        self.tokens = RefreshTokenRepository(session)

    # ── Hồ sơ cá nhân ─────────────────────────────────────────────────

    def update_profile(self, user: User, data: UpdateProfileRequest) -> User:
        """Cập nhật hồ sơ của CHÍNH người đang đăng nhập.

        `exclude_unset` chứ không phải `exclude_none`: client gửi
        `{"phone": null}` là CỐ Ý xoá số điện thoại, còn không gửi field nào
        mới là "giữ nguyên". Dùng nhầm thì người dùng không bao giờ xoá được
        dữ liệu đã nhập.
        """
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)

        logger.info(
            "cập nhật hồ sơ",
            extra={"extra_fields": {"user_id": str(user.id), "fields": sorted(changes)}},
        )
        return user

    # ── US-07: Quản trị người dùng ────────────────────────────────────

    def list_users(
        self,
        params: PageParams,
        *,
        q: str | None = None,
        role: UserRole | None = None,
        department_id: UUID | None = None,
        is_active: bool | None = None,
        sort_by: str = "createdAt",
        sort_desc: bool = True,
    ) -> tuple[list[User], int]:
        return self.users.list(
            params,
            role=role,
            department_id=department_id,
            is_active=is_active,
            q=q,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )

    def get_user(self, user_id: UUID) -> User:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Không tìm thấy người dùng")
        return user

    def create_user(self, actor: User, data: AdminCreateUserRequest) -> User:
        """Admin tạo tài khoản với vai trò bất kỳ.

        Đây là con đường DUY NHẤT để hệ thống có IT_AGENT và ADMIN: đăng ký
        tự phục vụ luôn gán EMPLOYEE (`auth/service.py`). Thiếu endpoint này
        thì mô hình ba vai trò của US-06 chỉ tồn tại trên giấy — muốn có một
        Agent phải sửa thẳng vào database.
        """
        email = data.email.strip().lower()
        if self.users.email_exists(email):
            # Cùng thông điệp với đăng ký tự phục vụ, không nói thêm gì về
            # tài khoản đã tồn tại.
            raise ConflictError("Email đã được sử dụng")

        self._assert_department_exists(data.department_id)

        user = self.users.add(
            User(
                email=email,
                full_name=data.full_name.strip(),
                password_hash=hash_password(data.password),
                role=data.role,
                department_id=data.department_id,
                phone=data.phone,
                is_active=True,
            )
        )
        self.db.commit()
        self.db.refresh(user)

        logger.info(
            "admin tạo người dùng",
            extra={
                "extra_fields": {
                    "actor_id": str(actor.id),
                    "user_id": str(user.id),
                    "role": str(user.role),
                }
            },
        )
        return user

    def admin_update(self, actor: User, user_id: UUID, data: AdminUpdateUserRequest) -> User:
        user = self.get_user(user_id)
        changes = data.model_dump(exclude_unset=True)

        new_role = changes.get("role")
        if new_role is not None and new_role != user.role:
            self._assert_admin_remains(user, becoming_admin=(new_role == UserRole.ADMIN))

        if "department_id" in changes:
            self._assert_department_exists(changes["department_id"])

        for field, value in changes.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)

        logger.info(
            "admin sửa người dùng",
            extra={
                "extra_fields": {
                    "actor_id": str(actor.id),
                    "user_id": str(user.id),
                    "fields": sorted(changes),
                }
            },
        )
        return user

    def set_active(self, actor: User, user_id: UUID, is_active: bool) -> User:
        """Khoá / mở khoá tài khoản. KHÔNG xoá cứng (BR-16).

        ★ Khoá phải THU HỒI TOÀN BỘ refresh token trong CÙNG transaction.
        Thiếu bước này, người vừa bị khoá vẫn đổi được access token mới suốt
        7 ngày tới — tức là việc khoá tài khoản không có tác dụng gì với đúng
        kịch bản cần nó nhất (nhân viên nghỉ việc, tài khoản bị chiếm).

        Access token đang cầm vẫn sống tối đa 15 phút — đánh đổi có chủ ý của
        ADR-0003. Nhưng `get_current_user` đọc `is_active` từ DB mỗi request,
        nên thực tế token đó chết ngay ở request kế tiếp.
        """
        user = self.get_user(user_id)

        if not is_active:
            if user.id == actor.id:
                raise ValidationError(
                    "Không thể tự khoá tài khoản của chính mình",
                    details={"userId": str(user_id)},
                )
            self._assert_admin_remains(user, becoming_admin=False)

        if user.is_active == is_active:
            return user  # không có gì đổi, không ghi log nhiễu

        user.is_active = is_active
        revoked = self.tokens.revoke_all_for_user(user.id) if not is_active else 0
        self.db.commit()
        self.db.refresh(user)

        logger.info(
            "khoá tài khoản" if not is_active else "mở khoá tài khoản",
            extra={
                "extra_fields": {
                    "actor_id": str(actor.id),
                    "user_id": str(user.id),
                    "revoked_tokens": revoked,
                }
            },
        )
        return user

    def list_departments(self) -> list[Department]:
        return self.departments.list_all()

    # ── Ràng buộc ─────────────────────────────────────────────────────

    def _assert_admin_remains(self, target: User, *, becoming_admin: bool) -> None:
        """Hệ thống phải luôn còn ít nhất một Admin đang hoạt động.

        Diễn đạt bằng bất biến chứ không bằng danh sách trường hợp: dù là tự
        hạ vai trò mình, hạ vai trò người khác, hay khoá tài khoản — câu hỏi
        luôn là "sau thao tác này còn Admin nào không". Một bất biến đúng
        chặn được cả những đường đi chưa ai nghĩ ra.
        """
        if becoming_admin or target.role != UserRole.ADMIN or not target.is_active:
            return

        if self.users.count_active_admins(exclude_id=target.id) == 0:
            raise ValidationError(
                "Đây là quản trị viên đang hoạt động cuối cùng — "
                "hãy chỉ định người khác làm Admin trước",
                details={"userId": str(target.id)},
            )

    def _assert_department_exists(self, department_id: UUID | None) -> None:
        if department_id is None:
            return
        if self.db.get(Department, department_id) is None:
            raise ValidationError(
                "Không tìm thấy phòng ban", details={"departmentId": str(department_id)}
            )
