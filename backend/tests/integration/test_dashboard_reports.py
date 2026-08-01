"""Báo cáo vận hành (F7 — US-37 → US-40).

Test dựng dữ liệu với MỐC THỜI GIAN TỰ ĐẶT thay vì dùng `now()`: các chỉ số ở
đây đều là hiệu của hai mốc, và một test phụ thuộc thời điểm chạy sẽ đỏ ngẫu
nhiên lúc 0 giờ hoặc khi CI chạy chậm.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from app.modules.reports.dashboard import DashboardService
from app.modules.tickets.constants import (
    ActorType,
    EventType,
    TicketPriority,
    TicketStatus,
)
from app.modules.tickets.models import Ticket, TicketEvent
from app.modules.users.constants import UserRole

MOC = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)
TU = MOC - timedelta(days=1)
DEN = MOC + timedelta(days=30)

# ★ Dấu `+` của múi giờ trong chuỗi ISO bị query string hiểu là DẤU CÁCH.
# Không mã hoá URL thì backend nhận "2026-07-14 08:00:00 00:00" và trả 422 —
# đúng cái bẫy mà `encodeURIComponent` ở frontend đang tránh.
KHOANG_THOI_GIAN = urlencode({"from": TU.isoformat(), "to": DEN.isoformat()})


@pytest.fixture
def nguoi_xu_ly(make_user):
    """★ Ràng buộc `ck_tickets_assignee` bắt mọi ticket ngoài NEW/CANCELLED
    phải có người xử lý. Đây là bất biến 1 ở tài liệu 03 §5, và database
    cưỡng chế nó — nên test không dựng được dữ liệu trái quy tắc dù muốn."""
    return make_user(role=UserRole.IT_AGENT, full_name="Agent Xử Lý Chính")


def them_ticket(
    db,
    requester,
    *,
    status=TicketStatus.NEW,
    priority=TicketPriority.MEDIUM,
    tao_luc=MOC,
    xong_luc=None,
    phan_hoi_luc=None,
    han_luc=None,
    assignee=None,
    category=None,
    tieu_de="Sự cố kiểm thử báo cáo",
) -> Ticket:
    ticket = Ticket(
        code=f"HD-TEST-{uuid4().hex[:8]}",
        title=tieu_de,
        description="Mô tả đủ dài để qua ràng buộc CHECK của bảng tickets.",
        status=status,
        priority=priority,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        category_id=category.id if category else None,
        created_at=tao_luc,
        updated_at=tao_luc,
        resolved_at=xong_luc,
        first_response_at=phan_hoi_luc,
        sla_resolution_due_at=han_luc,
        resolution_note="Đã xử lý xong sự cố" if xong_luc else None,
    )
    db.add(ticket)
    db.flush()
    return ticket


def them_su_kien_doi_trang_thai(db, ticket, *, tu_trang_thai, sang_trang_thai, luc):
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=None,
            actor_type=ActorType.SYSTEM,
            event_type=EventType.STATUS_CHANGED,
            field_name="status",
            old_value=str(tu_trang_thai),
            new_value=str(sang_trang_thai),
            created_at=luc,
        )
    )
    db.flush()


class TestUS37TongQuan:
    def test_dem_theo_trang_thai_va_muc_uu_tien(self, db, make_user, nguoi_xu_ly):
        nv = make_user()
        them_ticket(db, nv, status=TicketStatus.NEW, priority=TicketPriority.URGENT)
        them_ticket(db, nv, status=TicketStatus.NEW, priority=TicketPriority.LOW)
        them_ticket(
            db,
            nv,
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.LOW,
            assignee=nguoi_xu_ly,
        )

        bao_cao = DashboardService(db).overview(TU, DEN)
        theo_trang_thai = {b.key: b.count for b in bao_cao.by_status}
        theo_uu_tien = {b.key: b.count for b in bao_cao.by_priority}

        assert theo_trang_thai["NEW"] >= 2
        assert theo_trang_thai["IN_PROGRESS"] >= 1
        assert theo_uu_tien["URGENT"] >= 1
        assert theo_uu_tien["LOW"] >= 2
        assert bao_cao.total == sum(theo_trang_thai.values())

    def test_nhan_tieng_Viet_san_sang_de_ve_bieu_do(self, db, make_user, nguoi_xu_ly):
        them_ticket(db, make_user(), status=TicketStatus.PENDING_REQUESTER, assignee=nguoi_xu_ly)

        bao_cao = DashboardService(db).overview(TU, DEN)
        nhan = {b.key: b.label for b in bao_cao.by_status}

        assert nhan["PENDING_REQUESTER"] == "Chờ người yêu cầu"

    def test_ticket_XONG_SAU_HAN_van_bi_tinh_la_vi_pham(self, db, make_user, nguoi_xu_ly):
        """★ Vế hay bị quên nhất. Nếu chỉ đếm "quá hạn mà chưa xong", tỉ lệ vi
        phạm sẽ tự đẹp lên mỗi khi Agent đóng nốt các ticket đã trễ — một chỉ
        số thưởng cho việc giấu vấn đề."""
        nv = make_user()
        han = MOC + timedelta(hours=4)
        them_ticket(
            db,
            nv,
            status=TicketStatus.CLOSED,
            assignee=nguoi_xu_ly,
            han_luc=han,
            xong_luc=han + timedelta(hours=3),  # xong MUỘN 3 giờ
        )

        assert DashboardService(db).overview(TU, DEN).breached_total >= 1

    def test_xong_TRUOC_han_KHONG_bi_tinh_la_vi_pham(self, db, make_user, nguoi_xu_ly):
        han = MOC + timedelta(hours=4)
        them_ticket(
            db,
            make_user(),
            status=TicketStatus.CLOSED,
            assignee=nguoi_xu_ly,
            han_luc=han,
            xong_luc=han - timedelta(hours=1),
        )

        assert DashboardService(db).overview(TU, DEN).breached_total == 0

    def test_ti_le_vi_pham_la_None_khi_chua_co_ticket_nao(self, db):
        rong_tu = datetime(2020, 1, 1, tzinfo=UTC)
        bao_cao = DashboardService(db).overview(rong_tu, rong_tu + timedelta(days=1))

        # None = "chưa đủ dữ liệu", KHÁC hẳn 0 = "không vi phạm lần nào"
        assert bao_cao.total == 0
        assert bao_cao.breach_rate is None

    def test_dem_ticket_chua_co_nguoi_xu_ly(self, db, make_user, nguoi_xu_ly):
        nv = make_user()
        them_ticket(db, nv, status=TicketStatus.NEW)
        them_ticket(db, nv, status=TicketStatus.IN_PROGRESS, assignee=nguoi_xu_ly)

        assert DashboardService(db).overview(TU, DEN).unassigned_total >= 1

    def test_khoang_thoi_gian_nguoc_duoc_dao_lai(self, db):
        """Gõ nhầm ngày cho ra khoảng rỗng, và khoảng rỗng trông y hệt "không
        có việc gì xảy ra" — người dùng sẽ không nhận ra mình vừa nhập sai."""
        tu, den = DashboardService.resolve_window(DEN, TU)

        assert tu == TU and den == DEN


class TestUS38ThoiGianXuLy:
    def test_TRU_thoi_gian_cho_nguoi_yeu_cau_phan_hoi(
        self, db, make_user, ticket_category, nguoi_xu_ly
    ):
        """★ AC cốt lõi của US-38 và quy tắc 2 của tài liệu 03 §6.

        Ticket sống 10 giờ, trong đó 4 giờ nằm ở PENDING_REQUESTER chờ người
        dùng gửi ảnh chụp màn hình. Thời gian xử lý phải là 6 giờ, không phải
        10 — chờ khách không phải lỗi của Agent.
        """
        nv = make_user()
        ticket = them_ticket(
            db,
            nv,
            status=TicketStatus.CLOSED,
            assignee=nguoi_xu_ly,
            category=ticket_category,
            tao_luc=MOC,
            xong_luc=MOC + timedelta(hours=10),
        )
        them_su_kien_doi_trang_thai(
            db,
            ticket,
            tu_trang_thai=TicketStatus.IN_PROGRESS,
            sang_trang_thai=TicketStatus.PENDING_REQUESTER,
            luc=MOC + timedelta(hours=2),
        )
        them_su_kien_doi_trang_thai(
            db,
            ticket,
            tu_trang_thai=TicketStatus.PENDING_REQUESTER,
            sang_trang_thai=TicketStatus.IN_PROGRESS,
            luc=MOC + timedelta(hours=6),
        )

        dong = next(
            r
            for r in DashboardService(db).resolution_time(TU, DEN)
            if r.key == ticket_category.slug
        )

        assert dong.resolution_p50 == 360.0  # 6 giờ, KHÔNG phải 600

    def test_khong_co_khoang_cho_thi_giu_nguyen(self, db, make_user, ticket_category, nguoi_xu_ly):
        them_ticket(
            db,
            make_user(),
            status=TicketStatus.CLOSED,
            assignee=nguoi_xu_ly,
            category=ticket_category,
            tao_luc=MOC,
            xong_luc=MOC + timedelta(hours=3),
        )

        dong = next(
            r
            for r in DashboardService(db).resolution_time(TU, DEN)
            if r.key == ticket_category.slug
        )
        assert dong.resolution_p50 == 180.0

    def test_dung_TRUNG_VI_chu_khong_phai_trung_binh(
        self, db, make_user, ticket_category, nguoi_xu_ly
    ):
        """★ Lý do US-38 bắt dùng p50: một ticket bị bỏ quên làm trung bình
        gấp mấy lần, trong khi trung vị gần như không đổi.

        Ba ticket 1h, 2h, 300h ⇒ trung vị 2h (120 phút), trung bình hơn 100h.
        """
        nv = make_user()
        for gio in (1, 2, 300):
            them_ticket(
                db,
                nv,
                status=TicketStatus.CLOSED,
                assignee=nguoi_xu_ly,
                category=ticket_category,
                tao_luc=MOC,
                xong_luc=MOC + timedelta(hours=gio),
            )

        dong = next(
            r
            for r in DashboardService(db).resolution_time(TU, DEN)
            if r.key == ticket_category.slug
        )

        assert dong.resolution_p50 == 120.0
        assert dong.resolution_p90 > dong.resolution_p50

    def test_thoi_gian_phan_hoi_dau_tien_do_rieng(
        self, db, make_user, ticket_category, nguoi_xu_ly
    ):
        them_ticket(
            db,
            make_user(),
            status=TicketStatus.CLOSED,
            assignee=nguoi_xu_ly,
            category=ticket_category,
            tao_luc=MOC,
            phan_hoi_luc=MOC + timedelta(minutes=25),
            xong_luc=MOC + timedelta(hours=4),
        )

        dong = next(
            r
            for r in DashboardService(db).resolution_time(TU, DEN)
            if r.key == ticket_category.slug
        )

        assert dong.first_response_p50 == 25.0
        assert dong.resolution_p50 == 240.0

    def test_ticket_chua_xong_KHONG_lam_lech_bao_cao(
        self, db, make_user, ticket_category, nguoi_xu_ly
    ):
        them_ticket(
            db,
            make_user(),
            status=TicketStatus.IN_PROGRESS,
            assignee=nguoi_xu_ly,
            category=ticket_category,
        )

        dong = [
            r
            for r in DashboardService(db).resolution_time(TU, DEN)
            if r.key == ticket_category.slug
        ]
        assert dong == []


class TestUS39WorkloadTheoAgent:
    def test_agent_chua_co_viec_van_xuat_hien_voi_so_0(self, db, make_user):
        """Bảng workload mà thiếu người rảnh thì không dùng để cân đối phân
        công được — đúng mục đích của US-39."""
        agent_ranh = make_user(role=UserRole.IT_AGENT, full_name="Agent Đang Rảnh")

        dong = next(
            r for r in DashboardService(db).agent_workload(TU, DEN) if r.agent_id == agent_ranh.id
        )

        assert dong.open_tickets == 0
        assert dong.resolved_in_period == 0
        assert dong.avg_resolution_minutes is None
        assert dong.sla_breach_rate is None

    def test_dem_dung_viec_dang_mo_va_viec_da_xong_trong_ky(self, db, make_user):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        them_ticket(db, nv, status=TicketStatus.IN_PROGRESS, assignee=agent)
        them_ticket(db, nv, status=TicketStatus.NEW, assignee=agent, priority=TicketPriority.URGENT)
        them_ticket(
            db,
            nv,
            status=TicketStatus.CLOSED,
            assignee=agent,
            tao_luc=MOC,
            xong_luc=MOC + timedelta(hours=2),
        )

        dong = next(
            r for r in DashboardService(db).agent_workload(TU, DEN) if r.agent_id == agent.id
        )

        assert dong.open_tickets == 2
        assert dong.urgent_open == 1
        assert dong.resolved_in_period == 1
        assert dong.avg_resolution_minutes == 120.0

    def test_ti_le_vi_pham_sla_theo_tung_agent(self, db, make_user):
        nv = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        han = MOC + timedelta(hours=4)

        them_ticket(
            db,
            nv,
            status=TicketStatus.CLOSED,
            assignee=agent,
            han_luc=han,
            xong_luc=han + timedelta(hours=1),  # trễ
        )
        them_ticket(
            db,
            nv,
            status=TicketStatus.CLOSED,
            assignee=agent,
            han_luc=han,
            xong_luc=han - timedelta(hours=1),  # đúng hạn
        )

        dong = next(
            r for r in DashboardService(db).agent_workload(TU, DEN) if r.agent_id == agent.id
        )

        assert dong.resolved_in_period == 2
        assert dong.sla_breached == 1
        assert dong.sla_breach_rate == 0.5

    def test_diem_hai_long_la_None_khi_F8_chua_co_du_lieu(self, db, make_user):
        agent = make_user(role=UserRole.IT_AGENT)

        dong = next(
            r for r in DashboardService(db).agent_workload(TU, DEN) if r.agent_id == agent.id
        )

        assert dong.avg_rating is None
        assert dong.rating_count == 0


class TestUS40XuatCSV:
    def test_chan_CSV_injection(self, client, db, make_user, login):
        """★ Tiêu đề ticket là dữ liệu do NGƯỜI DÙNG nhập, và người mở file
        CSV lại chính là Admin. Ô bắt đầu bằng `=` sẽ được Excel chạy như
        công thức."""
        them_ticket(
            db,
            make_user(),
            tieu_de='=HYPERLINK("http://ke-tan-cong/","Bấm vào đây")',
        )

        c = login(make_user(role=UserRole.ADMIN))
        r = c.get(f"/api/v1/reports/tickets/export?{KHOANG_THOI_GIAN}")

        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        # Dấu nháy đơn phía trước buộc bảng tính đọc ô đó là văn bản
        assert "'=HYPERLINK" in r.text
        assert '"=HYPERLINK' not in r.text

    def test_co_BOM_va_dong_tieu_de(self, client, db, make_user, login):
        them_ticket(db, make_user())
        c = login(make_user(role=UserRole.ADMIN))

        r = c.get(f"/api/v1/reports/tickets/export?{KHOANG_THOI_GIAN}")

        assert r.text.startswith("﻿"), "thiếu BOM thì Excel hiện tiếng Việt thành ký tự lạ"
        assert "Mã ticket" in r.text
        assert "attachment" in r.headers["content-disposition"]


class TestPhanQuyenBaoCao:
    def test_nhan_vien_thuong_bi_tu_choi_moi_bao_cao(self, auth_client):
        for duong_dan in (
            "/api/v1/reports/overview",
            "/api/v1/reports/resolution-time",
            "/api/v1/reports/agent-workload",
            "/api/v1/reports/tickets/export",
        ):
            assert auth_client.get(duong_dan).status_code == 403, duong_dan

    def test_IT_AGENT_cung_bi_tu_choi_bao_cao_toan_he_thong(self, client, make_user, login):
        """US-37 → US-40 đều viết "Là Admin". Ma trận ở tài liệu 06 §5 có nhắc
        "Agent xem số liệu của chính mình" nhưng chưa story nào định nghĩa
        điều đó, nên chưa mở."""
        c = login(make_user(role=UserRole.IT_AGENT))

        assert c.get("/api/v1/reports/overview").status_code == 403
        assert c.get("/api/v1/reports/agent-workload").status_code == 403
        # `ai-accuracy` (US-22) thì Agent VẪN xem được — khác story, khác quyền
        assert c.get("/api/v1/reports/ai-accuracy").status_code == 200

    def test_admin_goi_duoc_va_tra_dung_hinh_dang(self, client, make_user, login):
        c = login(make_user(role=UserRole.ADMIN))

        r = c.get("/api/v1/reports/overview?refresh=true")
        assert r.status_code == 200
        body = r.json()
        for khoa in ("total", "openTotal", "breachedTotal", "byStatus", "byPriority", "daily"):
            assert khoa in body, khoa
