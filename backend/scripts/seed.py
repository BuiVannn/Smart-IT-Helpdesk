"""Nạp dữ liệu khởi tạo. PHẢI IDEMPOTENT — chạy nhiều lần không sinh trùng.

Chạy: docker compose exec api python scripts/seed.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.modules.knowledge.models import KbCategory  # noqa: E402
from app.modules.tickets.constants import TicketPriority  # noqa: E402
from app.modules.tickets.models import SlaPolicy, TicketCategory  # noqa: E402
from app.modules.users.constants import UserRole  # noqa: E402
from app.modules.users.models import Department, Holiday, User  # noqa: E402

DEPARTMENTS = [
    ("IT", "Phòng Công nghệ thông tin"),
    ("HR", "Phòng Nhân sự"),
    ("ACC", "Phòng Kế toán"),
    ("SALES", "Phòng Kinh doanh"),
    ("ENG", "Phòng Kỹ thuật"),
    ("MKT", "Phòng Marketing"),
]

TICKET_CATEGORIES = [
    ("network", "Mạng & Internet", TicketPriority.HIGH),
    ("hardware", "Phần cứng & Thiết bị", TicketPriority.MEDIUM),
    ("software", "Phần mềm & Ứng dụng", TicketPriority.MEDIUM),
    ("account", "Tài khoản & Mật khẩu", TicketPriority.MEDIUM),
    ("access", "Cấp quyền truy cập", TicketPriority.MEDIUM),
    ("email", "Email & Lịch", TicketPriority.MEDIUM),
    ("security", "Bảo mật", TicketPriority.URGENT),
    ("other", "Khác", TicketPriority.LOW),
]

SLA_POLICIES = [
    (TicketPriority.URGENT, 15, 240),
    (TicketPriority.HIGH, 60, 480),
    (TicketPriority.MEDIUM, 240, 1440),
    (TicketPriority.LOW, 480, 2400),
]

KB_CATEGORIES = [
    ("huong-dan-chung", "Hướng dẫn chung"),
    ("mang", "Mạng & Internet"),
    ("phan-mem", "Phần mềm"),
    ("tai-khoan", "Tài khoản"),
    ("bao-mat", "Bảo mật"),
]

HOLIDAYS_2026 = [
    (date(2026, 1, 1), "Tết Dương lịch"),
    (date(2026, 4, 30), "Ngày Giải phóng miền Nam"),
    (date(2026, 5, 1), "Quốc tế Lao động"),
    (date(2026, 9, 2), "Quốc khánh"),
]

# CHỈ dùng ở môi trường dev/staging. Production phải đổi mật khẩu.
DEV_USERS = [
    ("admin@company.com", "Quản trị viên", UserRole.ADMIN, "IT"),
    ("agent1@company.com", "Nguyễn Văn Kỹ Thuật", UserRole.IT_AGENT, "IT"),
    ("agent2@company.com", "Trần Thị Hỗ Trợ", UserRole.IT_AGENT, "IT"),
    ("employee1@company.com", "Lê Văn Nhân Viên", UserRole.EMPLOYEE, "ACC"),
    ("employee2@company.com", "Phạm Thị Kế Toán", UserRole.EMPLOYEE, "SALES"),
]
DEV_PASSWORD = "Password123"


def seed() -> None:
    with session_scope() as db:
        # Phòng ban
        for code, name in DEPARTMENTS:
            if not db.execute(
                select(Department).where(Department.code == code)
            ).scalar_one_or_none():
                db.add(Department(code=code, name=name))
        db.flush()

        # Loại sự cố
        for slug, name, priority in TICKET_CATEGORIES:
            if not db.execute(
                select(TicketCategory).where(TicketCategory.slug == slug)
            ).scalar_one_or_none():
                db.add(TicketCategory(slug=slug, name=name, default_priority=priority))

        # Chính sách SLA
        for priority, first, resolution in SLA_POLICIES:
            if not db.execute(
                select(SlaPolicy).where(SlaPolicy.priority == priority)
            ).scalar_one_or_none():
                db.add(SlaPolicy(
                    priority=priority,
                    first_response_minutes=first,
                    resolution_minutes=resolution,
                ))

        # Chủ đề kho tri thức
        for slug, name in KB_CATEGORIES:
            if not db.execute(
                select(KbCategory).where(KbCategory.slug == slug)
            ).scalar_one_or_none():
                db.add(KbCategory(slug=slug, name=name))

        # Ngày lễ
        for d, name in HOLIDAYS_2026:
            if not db.get(Holiday, d):
                db.add(Holiday(holiday_date=d, name=name))
        db.flush()

        # Người dùng dev
        depts = {d.code: d.id for d in db.execute(select(Department)).scalars().all()}
        for email, full_name, role, dept_code in DEV_USERS:
            if not db.execute(select(User).where(User.email == email)).scalar_one_or_none():
                db.add(User(
                    email=email,
                    full_name=full_name,
                    role=role,
                    department_id=depts.get(dept_code),
                    password_hash=hash_password(DEV_PASSWORD),
                ))

    print("✓ Đã nạp dữ liệu khởi tạo")
    print(f"  Tài khoản dev: admin@company.com / {DEV_PASSWORD}")


if __name__ == "__main__":
    seed()
