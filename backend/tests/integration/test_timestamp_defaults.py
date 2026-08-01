"""Chặn lỗi "giá trị mặc định thời gian bị đông cứng" tái diễn.

BỐI CẢNH: `0002_initial_schema` khai báo mười cột `created_at` bằng chuỗi
Python thường (`server_default='now()'`). SQLAlchemy hiểu chuỗi thường trên
cột DateTime là một GIÁ TRỊ, nên nó tính `now()` một lần lúc sinh migration và
ghi kết quả cố định vào DDL. Mọi bình luận, sự kiện ticket, tin nhắn chat đều
mang cùng một dấu thời gian — thời điểm migration được sinh ra.

Không test nào phát hiện được vì mỗi test chạy trong một transaction và không
test nào so sánh dấu thời gian của hai bản ghi tạo ở hai thời điểm khác nhau.
Bộ test xanh hoàn toàn trong khi lịch sử ticket hiển thị sai thứ tự.

Hai test dưới đây đánh vào chính khoảng trống đó: một test soi lược đồ, một
test đo hành vi thật.
"""

import time

import pytest
from sqlalchemy import select, text

from app.db import all_models  # noqa: F401
from app.modules.tickets.models import TicketEvent
from app.modules.users.constants import UserRole

# Bắt cả `'2026-...'::timestamptz` lẫn `'2026-...'::timestamp`.
FROZEN_DEFAULT_PATTERN = r"^'\d{4}-\d{2}-\d{2}[ T]"


def test_khong_cot_nao_co_gia_tri_mac_dinh_la_hang_thoi_gian(db):
    """Quét toàn bộ lược đồ, không chỉ những bảng đã biết là hỏng.

    Viết dưới dạng quét lược đồ có chủ ý: một test chỉ liệt kê mười bảng đã
    biết sẽ không bắt được bảng thứ mười một mà người khác thêm sau này bằng
    đúng cách viết sai đó.
    """
    rows = db.execute(
        text(
            "SELECT table_name, column_name, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_default ~ :pattern "
            "ORDER BY table_name, column_name"
        ),
        {"pattern": FROZEN_DEFAULT_PATTERN},
    ).all()

    assert rows == [], (
        "Các cột sau có giá trị mặc định là một mốc thời gian cố định thay vì "
        "now(). Dùng sa.text('now()') hoặc func.now(), đừng dùng chuỗi thường "
        "'now()':\n" + "\n".join(f"  {t}.{c} = {d}" for t, c, d in rows)
    )


def test_hai_ban_ghi_tao_cach_nhau_co_dau_thoi_gian_khac_nhau(
    db, make_user, sla_policies, ticket_category
):
    """Kiểm chứng HÀNH VI, không chỉ lược đồ.

    ★ Bẫy quan trọng: PostgreSQL `now()` trả về thời điểm BẮT ĐẦU TRANSACTION,
    nên trong cùng một transaction test, hai bản ghi vẫn có dấu thời gian
    giống hệt nhau kể cả khi default đã đúng. Vì vậy test này so với
    `clock_timestamp()` — đồng hồ thật — chứ không so hai bản ghi với nhau.
    """
    from app.modules.tickets.constants import EventType
    from app.modules.tickets.schemas import CreateTicketRequest
    from app.modules.tickets.service import TicketService

    user = make_user(role=UserRole.EMPLOYEE)
    service = TicketService(db)
    ticket = service.create(
        user,
        CreateTicketRequest.model_validate(
            {
                "title": "Ticket kiểm tra dấu thời gian",
                "description": "Nội dung đủ dài để qua ràng buộc CHECK của database.",
            }
        ),
    )
    time.sleep(0.01)

    event = db.execute(
        select(TicketEvent).where(
            TicketEvent.ticket_id == ticket.id,
            TicketEvent.event_type == EventType.CREATED,
        )
    ).scalar_one()

    lech_giay = db.execute(
        text("SELECT EXTRACT(EPOCH FROM (clock_timestamp() - :moment))"),
        {"moment": event.created_at},
    ).scalar_one()

    assert abs(float(lech_giay)) < 60, (
        f"created_at lệch {lech_giay:.0f} giây so với đồng hồ thật — giá trị "
        "mặc định nhiều khả năng lại là một hằng số thời gian"
    )


@pytest.mark.parametrize(
    "table",
    [
        "ai_classifications",
        "article_chunks",
        "chat_feedback",
        "chat_messages",
        "chat_sessions",
        "idempotency_keys",
        "notifications",
        "ticket_attachments",
        "ticket_comments",
        "ticket_events",
    ],
)
def test_muoi_bang_tung_hong_nay_da_dung_now(db, table):
    """Danh sách chính xác mười bảng mà migration 0005 đã vá."""
    default = db.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = 'created_at'"
        ),
        {"table": table},
    ).scalar_one_or_none()

    assert default is not None, f"{table}.created_at không còn giá trị mặc định"
    assert "now()" in default, f"{table}.created_at đang là {default!r}"
