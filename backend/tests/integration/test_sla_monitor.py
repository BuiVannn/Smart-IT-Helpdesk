"""Job nhắc trước hạn SLA (US-35).

AC khó nhất của story này không phải là "gửi được thông báo" mà là **chạy lại
nhiều lần không sinh trùng** và **bắt kịp sau khi hệ thống tắt một thời
gian**. Cả hai đều được kiểm ở đây.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.notifications.models import Notification
from app.modules.notifications.sla_monitor import SlaMonitor
from app.modules.tickets.constants import EventType, TicketStatus
from app.modules.tickets.models import Ticket, TicketEvent
from app.modules.users.constants import UserRole
from app.modules.users.models import User

BAY_GIO = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)


@pytest.fixture
def don_sach_admin(db):
    """Vô hiệu hoá Admin có sẵn từ seed để đếm được chính xác ai nhận thông báo."""
    for u in db.execute(select(User).where(User.role == UserRole.ADMIN)).scalars().all():
        u.is_active = False
    db.flush()


def them_ticket(db, requester, assignee, *, han, tao_luc=None, trang_thai=TicketStatus.IN_PROGRESS):
    ticket = Ticket(
        code=f"HD-SLA-{uuid4().hex[:8]}",
        title="Sự cố cần theo dõi hạn xử lý",
        description="Mô tả đủ dài để qua ràng buộc CHECK của bảng tickets.",
        status=trang_thai,
        requester_id=requester.id,
        assignee_id=assignee.id,
        created_at=tao_luc or (han - timedelta(hours=4)),
        sla_resolution_due_at=han,
    )
    db.add(ticket)
    db.flush()
    return ticket


def thong_bao_cua(db, user_id, loai):
    return (
        db.execute(
            select(Notification).where(Notification.user_id == user_id, Notification.type == loai)
        )
        .scalars()
        .all()
    )


class TestBaoDaTreHan:
    def test_bao_cho_ca_assignee_va_admin(self, db, make_user, don_sach_admin):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)
        ticket = them_ticket(db, nv, agent, han=BAY_GIO - timedelta(hours=2))

        ket_qua = SlaMonitor(db).run(now=BAY_GIO)

        assert ket_qua.breached == 1
        assert len(thong_bao_cua(db, agent.id, "SLA_BREACHED")) == 1
        # ★ Assignee nghỉ phép là nguyên nhân phổ biến nhất khiến ticket trễ,
        # nên báo mỗi assignee là báo đúng người không xử lý được.
        assert len(thong_bao_cua(db, admin.id, "SLA_BREACHED")) == 1
        assert ticket.sla_breached_at == BAY_GIO

    def test_ghi_su_kien_vao_nhat_ky_ticket(self, db, make_user, don_sach_admin):
        """Thông báo bị đánh dấu đã đọc rồi quên; nhật ký thì không (BR-17)."""
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        ticket = them_ticket(db, nv, agent, han=BAY_GIO - timedelta(hours=2))

        SlaMonitor(db).run(now=BAY_GIO)

        su_kien = (
            db.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket.id,
                    TicketEvent.event_type == EventType.SLA_BREACHED,
                )
            )
            .scalars()
            .all()
        )
        assert len(su_kien) == 1
        assert su_kien[0].actor_id is None  # do hệ thống ghi, không phải người

    def test_ticket_chua_giao_cho_ai_van_bao_cho_Admin(self, db, make_user, don_sach_admin):
        """Ticket NEW quá hạn mà không ai được báo là kịch bản tệ nhất: không
        có assignee thì không có ai nhận cảnh báo, và nó nằm im mãi."""
        nv = make_user()
        admin = make_user(role=UserRole.ADMIN)
        ticket = Ticket(
            code=f"HD-SLA-{uuid4().hex[:8]}",
            title="Ticket chưa ai nhận và đã quá hạn",
            description="Mô tả đủ dài để qua ràng buộc CHECK của bảng tickets.",
            status=TicketStatus.NEW,
            requester_id=nv.id,
            created_at=BAY_GIO - timedelta(hours=6),
            sla_resolution_due_at=BAY_GIO - timedelta(hours=2),
        )
        db.add(ticket)
        db.flush()

        SlaMonitor(db).run(now=BAY_GIO)

        assert len(thong_bao_cua(db, admin.id, "SLA_BREACHED")) == 1


class TestNhacSapTreHan:
    def test_con_duoi_25_phan_tram_thi_nhac_assignee(self, db, make_user, don_sach_admin):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        # Sống 10 giờ, còn 1 giờ ⇒ còn 10% thời gian
        ticket = them_ticket(
            db,
            nv,
            agent,
            tao_luc=BAY_GIO - timedelta(hours=9),
            han=BAY_GIO + timedelta(hours=1),
        )

        ket_qua = SlaMonitor(db).run(now=BAY_GIO)

        assert ket_qua.at_risk == 1
        assert len(thong_bao_cua(db, agent.id, "SLA_AT_RISK")) == 1
        assert ticket.sla_warned_at == BAY_GIO

    def test_con_nhieu_thoi_gian_thi_KHONG_nhac(self, db, make_user, don_sach_admin):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        them_ticket(
            db,
            nv,
            agent,
            tao_luc=BAY_GIO - timedelta(hours=1),
            han=BAY_GIO + timedelta(hours=9),
        )

        ket_qua = SlaMonitor(db).run(now=BAY_GIO)

        assert ket_qua.at_risk == 0
        assert thong_bao_cua(db, agent.id, "SLA_AT_RISK") == []

    def test_da_qua_han_thi_bao_TRE_chu_khong_bao_SAP_TRE(self, db, make_user, don_sach_admin):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        them_ticket(db, nv, agent, han=BAY_GIO - timedelta(hours=1))

        SlaMonitor(db).run(now=BAY_GIO)

        assert len(thong_bao_cua(db, agent.id, "SLA_BREACHED")) == 1
        assert thong_bao_cua(db, agent.id, "SLA_AT_RISK") == []


class TestChayLaiKhongSinhTrung:
    def test_chay_ba_lan_van_chi_mot_thong_bao(self, db, make_user, don_sach_admin):
        """★ AC bắt buộc của US-35. Job chạy mỗi 5 phút — không idempotent thì
        một ticket trễ hạn qua đêm sẽ sinh 288 thông báo, và người dùng sẽ tắt
        thông báo vĩnh viễn."""
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        them_ticket(db, nv, agent, han=BAY_GIO - timedelta(hours=2))

        lan_1 = SlaMonitor(db).run(now=BAY_GIO)
        lan_2 = SlaMonitor(db).run(now=BAY_GIO + timedelta(minutes=5))
        lan_3 = SlaMonitor(db).run(now=BAY_GIO + timedelta(minutes=10))

        assert (lan_1.breached, lan_2.breached, lan_3.breached) == (1, 0, 0)
        assert len(thong_bao_cua(db, agent.id, "SLA_BREACHED")) == 1

    def test_ticket_da_nhac_SAP_TRE_van_bao_duoc_khi_THUC_SU_TRE(
        self, db, make_user, don_sach_admin
    ):
        """Hai cảnh báo là hai loại khác nhau — đã nhắc "sắp trễ" không được
        nuốt mất tin "đã trễ"."""
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        han = BAY_GIO + timedelta(hours=1)
        them_ticket(db, nv, agent, tao_luc=BAY_GIO - timedelta(hours=9), han=han)

        SlaMonitor(db).run(now=BAY_GIO)
        sau = SlaMonitor(db).run(now=han + timedelta(minutes=30))

        assert sau.breached == 1
        assert len(thong_bao_cua(db, agent.id, "SLA_AT_RISK")) == 1
        assert len(thong_bao_cua(db, agent.id, "SLA_BREACHED")) == 1


class TestBatKipSauKhiHeThongTat:
    def test_phat_hien_dung_ticket_da_tre_trong_luc_job_khong_chay(
        self, db, make_user, don_sach_admin
    ):
        """★ AC cuối của US-35. Job KHÔNG lưu mốc chạy lần trước — nó hỏi
        "ticket nào đang quá hạn mà chưa báo", nên tắt máy bao lâu cũng không
        bỏ sót."""
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        them_ticket(db, nv, agent, han=BAY_GIO - timedelta(days=3))

        # Job không chạy suốt ba ngày, giờ mới bật lại
        ket_qua = SlaMonitor(db).run(now=BAY_GIO)

        assert ket_qua.breached == 1


class TestKhongLamPhienVoIch:
    def test_ticket_da_xu_ly_xong_KHONG_bi_bao(self, db, make_user, don_sach_admin):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        ticket = them_ticket(
            db, nv, agent, han=BAY_GIO - timedelta(hours=2), trang_thai=TicketStatus.IN_PROGRESS
        )
        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = BAY_GIO - timedelta(hours=3)
        ticket.resolution_note = "Đã xử lý xong trước hạn"
        db.flush()

        ket_qua = SlaMonitor(db).run(now=BAY_GIO)

        assert ket_qua.breached == 0
        assert thong_bao_cua(db, agent.id, "SLA_BREACHED") == []

    def test_ticket_chua_co_han_SLA_bi_bo_qua(self, db, make_user, don_sach_admin):
        """Không khẳng định `scanned == 0`: database dùng chung có sẵn ticket
        của test khác và của dữ liệu seed. Khẳng định phải nói về ĐÚNG ticket
        này, nếu không nó chỉ đo được rằng database đang rỗng."""
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        ticket = them_ticket(db, nv, agent, han=BAY_GIO - timedelta(hours=2))
        ticket.sla_resolution_due_at = None
        db.flush()

        monitor = SlaMonitor(db)
        assert ticket.id not in {t.id for t in monitor._candidates()}

        monitor.run(now=BAY_GIO)
        assert thong_bao_cua(db, agent.id, "SLA_BREACHED") == []
