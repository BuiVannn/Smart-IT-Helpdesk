"""Sửa giá trị mặc định `created_at` bị đông cứng thành một mốc thời gian.

BỐI CẢNH — lỗi này im lặng và nghiêm trọng. Trong `0002_initial_schema`, mười
cột `created_at` được khai báo bằng chuỗi Python thường:

    server_default='now()'      # SAI

SQLAlchemy hiểu chuỗi thường trên cột DateTime là một GIÁ TRỊ, không phải
biểu thức SQL, nên nó tính `now()` MỘT LẦN lúc sinh migration rồi ghi kết quả
vào DDL:

    DEFAULT '2026-07-31 14:29:15.953444+00'::timestamptz

Hậu quả: mọi bản ghi bình luận, sự kiện ticket, tin nhắn chat, thông báo,
chunk tài liệu và bản ghi phân loại AI đều mang CÙNG MỘT dấu thời gian — thời
điểm migration được sinh ra. Cụ thể:

- US-17 (lịch sử ticket) và US-15 (bình luận) sắp xếp theo `created_at` ⇒
  thứ tự hiển thị là ngẫu nhiên, không phải thứ tự xảy ra.
- US-24 (hội thoại chatbot) mất thứ tự tin nhắn.
- US-22 (độ chính xác AI "theo tuần") gom toàn bộ vào một tuần duy nhất.

Bộ test không phát hiện được vì mỗi test chạy trong một transaction và không
test nào so sánh dấu thời gian giữa hai bản ghi tạo ở hai thời điểm khác nhau.
Cách đúng là `sa.text('now()')` hoặc `func.now()` — sáu cột dùng cách này nên
chúng không bị ảnh hưởng.

`tests/integration/test_timestamp_defaults.py` chặn lỗi tái diễn bằng cách quét
`information_schema` tìm mọi giá trị mặc định là hằng thời gian.

Revision ID: 0005
Revises: 0004
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mười cột bị ảnh hưởng. Sáu cột còn lại trong 0002 đã dùng sa.text('now()').
FROZEN_COLUMNS: tuple[tuple[str, str], ...] = (
    ("ai_classifications", "created_at"),
    ("article_chunks", "created_at"),
    ("chat_feedback", "created_at"),
    ("chat_messages", "created_at"),
    ("chat_sessions", "created_at"),
    ("idempotency_keys", "created_at"),
    ("notifications", "created_at"),
    ("ticket_attachments", "created_at"),
    ("ticket_comments", "created_at"),
    ("ticket_events", "created_at"),
)


def upgrade() -> None:
    for table, column in FROZEN_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now()")

    # KHÔNG sửa dữ liệu cũ. Dấu thời gian thật của các bản ghi đã ghi sai là
    # thông tin đã mất — đoán lại sẽ tạo ra một lịch sử trông đáng tin nhưng
    # bịa đặt, tệ hơn cả việc để lộ ra là nó sai. Môi trường phát triển nên
    # seed lại: python scripts/seed.py


def downgrade() -> None:
    # Quay lại giá trị đông cứng là vô nghĩa; bỏ hẳn default là trạng thái
    # trung thực hơn của "trước bản vá này".
    for table, column in FROZEN_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
