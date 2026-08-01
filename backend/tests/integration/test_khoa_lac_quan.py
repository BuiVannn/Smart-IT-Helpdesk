"""Khoá lạc quan trên ticket (docs/design/03 §7, BR-16).

★ TEST NÀY KHÔNG DÙNG FIXTURE `db`.

Fixture `db` chạy mọi thứ trong MỘT transaction rồi rollback, nên nó không
bao giờ dựng được tình huống tranh chấp: hai người sửa cùng lúc là hai
transaction khác nhau. Bản test cũ của `claim()` gọi tuần tự trong một
session và chỉ khẳng định `version == 2` — nó xanh trong suốt thời gian
khoá lạc quan HOÀN TOÀN VÔ HIỆU.

Ở đây mỗi "người dùng" có session riêng, dữ liệu được commit thật, và được
dọn trong `finally`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import hash_password
from app.db import all_models  # noqa: F401
from app.db.session import engine
from app.modules.notifications.models import Notification
from app.modules.tickets.constants import TicketStatus
from app.modules.tickets.models import Ticket, TicketEvent
from app.modules.users.constants import UserRole
from app.modules.users.models import User

PhienRieng = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def san_khau():
    """Dựng một ticket đã commit thật, dọn sạch sau khi test xong."""
    try:
        engine.connect().close()
    except Exception as exc:  # pragma: no cover - môi trường không có database
        pytest.skip(f"Không kết nối được database: {type(exc).__name__}")

    dau = uuid4().hex[:8]
    setup: Session = PhienRieng()
    nguoi_yeu_cau = User(
        email=f"lock-req-{dau}@company.com",
        full_name="Người Yêu Cầu Kiểm Thử Khoá",
        password_hash=hash_password("MatKhau123"),
        role=UserRole.EMPLOYEE,
    )
    agent_mot = User(
        email=f"lock-a1-{dau}@company.com",
        full_name="Agent Một",
        password_hash=hash_password("MatKhau123"),
        role=UserRole.IT_AGENT,
    )
    agent_hai = User(
        email=f"lock-a2-{dau}@company.com",
        full_name="Agent Hai",
        password_hash=hash_password("MatKhau123"),
        role=UserRole.IT_AGENT,
    )
    setup.add_all([nguoi_yeu_cau, agent_mot, agent_hai])
    setup.flush()

    ticket = Ticket(
        code=f"HD-LOCK-{dau}",
        title="Ticket dùng để kiểm chứng khoá lạc quan",
        description="Bản ghi này được tạo và xoá trong cùng một test.",
        status=TicketStatus.NEW,
        requester_id=nguoi_yeu_cau.id,
        created_at=datetime.now(UTC),
    )
    setup.add(ticket)
    setup.commit()

    ids = (ticket.id, agent_mot.id, agent_hai.id, nguoi_yeu_cau.id)
    setup.close()

    yield ids

    don: Session = PhienRieng()
    ticket_id, *user_ids = ids
    don.execute(delete(Notification).where(Notification.entity_id == ticket_id))
    don.execute(delete(TicketEvent).where(TicketEvent.ticket_id == ticket_id))
    don.execute(delete(Ticket).where(Ticket.id == ticket_id))
    don.execute(delete(User).where(User.id.in_(user_ids)))
    don.commit()
    don.close()


class TestHaiNguoiSuaCungLuc:
    def test_nguoi_thu_hai_bi_CHAN_chu_khong_ghi_de_im_lang(self, san_khau):
        """★ Kịch bản đã phá được bản cũ: hai Agent cùng bấm "Nhận việc".

        Cả hai đọc `version = 1`, cả hai qua được bước so sánh trong Python,
        cả hai UPDATE. Không có `WHERE version = 1` thì người sau ghi đè im
        lặng lên người trước — Agent Một nhận HTTP 200 và thấy mình là người
        xử lý, trong khi database ghi Agent Hai.
        """
        ticket_id, agent_mot, agent_hai, _ = san_khau

        phien_a: Session = PhienRieng()
        phien_b: Session = PhienRieng()
        try:
            # Cả hai cùng mở ticket — cùng đọc version 1
            ticket_a = phien_a.get(Ticket, ticket_id)
            ticket_b = phien_b.get(Ticket, ticket_id)
            assert ticket_a.version == ticket_b.version == 1

            # Agent Hai bấm trước và thắng
            ticket_b.assignee_id = agent_hai
            ticket_b.status = TicketStatus.ASSIGNED
            phien_b.commit()

            # Agent Một bấm sau — phải BỊ CHẶN, không được ghi đè
            ticket_a.assignee_id = agent_mot
            ticket_a.status = TicketStatus.ASSIGNED
            with pytest.raises(StaleDataError):
                phien_a.commit()
        finally:
            phien_a.rollback()
            phien_a.close()
            phien_b.close()

        kiem: Session = PhienRieng()
        try:
            cuoi = kiem.get(Ticket, ticket_id)
            assert cuoi.assignee_id == agent_hai, "người thắng phải là người bấm trước"
            assert cuoi.version == 2
        finally:
            kiem.close()

    def test_version_tang_dung_MOT_lan_moi_lan_ghi(self, san_khau):
        """Bản cũ cộng tay trong service nên hai lần ghi đồng thời chỉ làm
        version lên 2 thay vì 3 — một lần cộng bị mất, và lần tranh chấp kế
        tiếp lại lọt."""
        ticket_id, agent_mot, _, _ = san_khau

        for lan in range(1, 4):
            phien: Session = PhienRieng()
            try:
                t = phien.get(Ticket, ticket_id)
                assert t.version == lan
                t.title = f"Đổi tiêu đề lần {lan} để tạo thay đổi thật"
                phien.commit()
                assert t.version == lan + 1
            finally:
                phien.close()

    def test_khong_co_thay_doi_thi_khong_tang_version(self, san_khau):
        """Đọc rồi commit mà không sửa gì thì version phải đứng yên — nếu
        không, mọi lần mở trang chi tiết sẽ làm phiên bản trôi và người dùng
        nhận lỗi xung đột vô cớ."""
        ticket_id, *_ = san_khau

        phien: Session = PhienRieng()
        try:
            t = phien.get(Ticket, ticket_id)
            truoc = t.version
            phien.commit()
            assert t.version == truoc
        finally:
            phien.close()


class TestQuaDuongHTTP:
    def test_gui_version_cu_nhan_409(self, client, make_user, login, sla_policies):
        """Tầng HTTP vẫn phải trả 409 kèm phiên bản hiện tại để frontend hiển
        thị được hướng dẫn cụ thể, thay vì để `StaleDataError` rơi ra 500."""
        nhan_vien = make_user()
        c = login(nhan_vien)
        ticket = c.post(
            "/api/v1/tickets",
            json={
                "title": "Ticket kiểm chứng phiên bản qua HTTP",
                "description": "Mô tả đủ dài để qua ràng buộc của bảng tickets.",
            },
        ).json()

        r = c.patch(
            f"/api/v1/tickets/{ticket['id']}",
            json={"title": "Tiêu đề mới hoàn toàn hợp lệ", "version": ticket["version"] + 5},
        )

        assert r.status_code == 409
        assert r.json()["error"]["details"]["currentVersion"] == ticket["version"]


class TestNguonSuThat:
    def test_model_Ticket_khai_bao_version_id_col(self):
        """Chốt lại bằng một khẳng định trực tiếp trên metadata.

        Nếu ai đó xoá `__mapper_args__` khi refactor, các test trên vẫn có thể
        đỏ theo cách khó đọc. Test này chỉ thẳng vào nguyên nhân.
        """
        from sqlalchemy import inspect

        assert inspect(Ticket).version_id_col is not None, (
            "Ticket mất `__mapper_args__ = {'version_id_col': version}` — "
            "khoá lạc quan trở lại thành đọc-rồi-ghi"
        )
        assert inspect(Ticket).version_id_col.name == "version"


def _khong_dung(_: Session):  # pragma: no cover - giữ import select khỏi bị dọn
    return select(Ticket)
