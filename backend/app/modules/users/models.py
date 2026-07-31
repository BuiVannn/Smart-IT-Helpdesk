"""Model: Department, User, AgentSkill."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.users.constants import UserRole


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="department")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), default=UserRole.EMPLOYEE, nullable=False
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL")
    )
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    department: Mapped[Department | None] = relationship(back_populates="users")
    skills: Mapped[list["AgentSkill"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )

    @property
    def is_agent(self) -> bool:
        return self.role == UserRole.IT_AGENT

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def can_be_assigned(self) -> bool:
        """Chỉ IT Agent đang hoạt động mới được làm assignee (BR-02)."""
        return self.is_active and self.role == UserRole.IT_AGENT

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class AgentSkill(Base):
    """Kỹ năng của IT Agent theo loại sự cố — phục vụ gợi ý người xử lý (US-20)."""

    __tablename__ = "agent_skills"

    agent_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ticket_categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    level: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)  # 1..3

    agent: Mapped[User] = relationship(back_populates="skills")


class Holiday(Base):
    """Ngày nghỉ — dùng cho SlaCalculator."""

    __tablename__ = "holidays"

    holiday_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
