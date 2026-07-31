"""Bật các extension PostgreSQL cần thiết.

Đây là migration ĐẦU TIÊN và phải chạy trước mọi thứ khác:
- vector   : lưu embedding cho RAG (ADR-0005)
- citext   : email so sánh không phân biệt hoa/thường
- unaccent : gõ "mat khau" tìm ra "mật khẩu" (ADR-0004)
- pg_trgm  : tìm gần đúng theo tên người dùng

Revision ID: 0001
Revises:
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ["uuid-ossp", "citext", "pg_trgm", "unaccent", "vector"]


def upgrade() -> None:
    for ext in EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')


def downgrade() -> None:
    # Không xoá extension: các bảng khác có thể vẫn đang dùng kiểu dữ liệu của chúng.
    pass
