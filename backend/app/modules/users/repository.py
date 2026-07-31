"""★ FILE MẪU — copy cấu trúc này khi viết repository.py cho module khác.

Quy tắc:
- Nhận Session qua constructor, KHÔNG tự tạo session
- CHỈ truy vấn và ánh xạ — không chứa logic nghiệp vụ
- Trả về model/entity, KHÔNG trả về Pydantic schema
- KHÔNG commit — việc mở/đóng transaction là của service
"""

from __future__ import annotations

# ⚠️ Dòng trên là BẮT BUỘC ở file này: phương thức `list()` che mất builtin
# `list` trong phạm vi class, nên annotation `-> list[User]` viết sau nó sẽ nổ
# `TypeError: 'function' object is not subscriptable`. Hoãn đánh giá annotation
# là cách sửa gọn nhất mà vẫn giữ được tên phương thức tự nhiên.
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.pagination import PageParams
from app.modules.users.constants import UserRole
from app.modules.users.models import Department, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()   # để lấy id, nhưng KHÔNG commit
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.department))
            .where(User.id == user_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        # CITEXT nên không cần lower() — database tự so sánh không phân biệt hoa/thường
        stmt = select(User).where(User.email == email)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        params: PageParams,
        *,
        role: UserRole | None = None,
        department_id: UUID | None = None,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[User], int]:
        """Trả về (danh sách, tổng số) — tổng số cần cho phân trang."""
        stmt: Select = select(User).options(selectinload(User.department))

        if role is not None:
            stmt = stmt.where(User.role == role)
        if department_id is not None:
            stmt = stmt.where(User.department_id == department_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(User.full_name.ilike(pattern) | User.email.ilike(pattern))

        total = self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        rows = self.session.execute(
            stmt.order_by(User.created_at.desc()).offset(params.offset).limit(params.limit)
        ).scalars().all()

        return list(rows), total

    def list_active_agents(self) -> list[User]:
        """IT Agent đang hoạt động — dùng cho gợi ý người xử lý (US-20)."""
        stmt = select(User).where(
            User.role == UserRole.IT_AGENT, User.is_active.is_(True)
        ).order_by(User.full_name)
        return list(self.session.execute(stmt).scalars().all())

    def email_exists(self, email: str) -> bool:
        return self.session.execute(
            select(func.count()).select_from(User).where(User.email == email)
        ).scalar_one() > 0


class DepartmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, include_inactive: bool = False) -> list[Department]:
        stmt = select(Department).order_by(Department.name)
        if not include_inactive:
            stmt = stmt.where(Department.is_active.is_(True))
        return list(self.session.execute(stmt).scalars().all())

    def get_by_code(self, code: str) -> Department | None:
        return self.session.execute(
            select(Department).where(Department.code == code)
        ).scalar_one_or_none()
