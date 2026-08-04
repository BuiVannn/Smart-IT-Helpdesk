"""Báo cáo tổng hợp điểm hài lòng (F8 — US-42).

Cùng phong cách với `test_dashboard_reports.py`: mốc thời gian TỰ ĐẶT, không
dùng `now()`, để test không đỏ ngẫu nhiên theo giờ chạy CI.

Test ở đây gọi thẳng `SatisfactionService` (không qua HTTP) cho phần nghiệp
vụ — giống `DashboardService` ở file kia — và có thêm một lớp test HTTP
riêng để khoá lại việc mount route, quyền Admin, và hình dạng JSON trả về.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.feedback.models import TicketRating
from app.modules.reports.satisfaction import SatisfactionService
from app.modules.tickets.constants import TicketPriority, TicketStatus
from app.modules.tickets.models import Ticket, TicketCategory
from app.modules.users.constants import UserRole

MOC = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)
TU = MOC - timedelta(days=1)
DEN = MOC + timedelta(days=30)


@pytest.fixture
def agent_a(make_user):
    return make_user(role=UserRole.IT_AGENT, full_name="Agent A")


@pytest.fixture
def agent_b(make_user):
    return make_user(role=UserRole.IT_AGENT, full_name="Agent B")


def them_ticket_da_dong(
    db,
    requester,
    *,
    assignee,
    category=None,
    xong_luc=MOC,
) -> Ticket:
    """Ticket đã đóng — mẫu số của tỉ lệ phản hồi, tách khỏi việc có/không
    có đánh giá đi kèm (hai việc độc lập với nhau)."""
    ticket = Ticket(
        code=f"HD-TEST-{uuid4().hex[:8]}",
        title="Sự cố kiểm thử điểm hài lòng",
        description="Mô tả đủ dài để qua ràng buộc CHECK của bảng tickets.",
        status=TicketStatus.CLOSED,
        priority=TicketPriority.MEDIUM,
        requester_id=requester.id,
        assignee_id=assignee.id,
        category_id=category.id if category else None,
        created_at=xong_luc - timedelta(hours=2),
        updated_at=xong_luc,
        resolved_at=xong_luc,
        closed_at=xong_luc,
        resolution_note="Đã xử lý xong sự cố",
    )
    db.add(ticket)
    db.flush()
    return ticket


def them_danh_gia(db, ticket, rater, *, score, comment=None, luc=MOC) -> TicketRating:
    rating = TicketRating(
        ticket_id=ticket.id,
        rater_id=rater.id,
        agent_id=ticket.assignee_id,
        score=score,
        comment=comment,
        created_at=luc,
    )
    db.add(rating)
    db.flush()
    return rating


class TestTongTheHaiLong:
    def test_diem_trung_binh_va_phan_bo(self, db, make_user, agent_a):
        nv = make_user()
        t1 = them_ticket_da_dong(db, nv, assignee=agent_a)
        t2 = them_ticket_da_dong(db, nv, assignee=agent_a)
        them_danh_gia(db, t1, nv, score=5)
        them_danh_gia(db, t2, nv, score=3)

        overall = SatisfactionService(db).report(TU, DEN).overall

        assert overall.rating_count == 2
        assert overall.avg_score == 4.0
        assert overall.distribution[5] == 1
        assert overall.distribution[3] == 1
        assert overall.distribution[1] == 0

    def test_ti_le_phan_hoi_la_ratings_chia_cho_ticket_da_dong(self, db, make_user, agent_a):
        """★ AC 2 của US-42: mẫu số là ticket ĐÃ ĐÓNG, không phải tổng ticket."""
        nv = make_user()
        t1 = them_ticket_da_dong(db, nv, assignee=agent_a)
        them_ticket_da_dong(db, nv, assignee=agent_a)  # ticket đóng nhưng KHÔNG được đánh giá
        them_danh_gia(db, t1, nv, score=4)

        overall = SatisfactionService(db).report(TU, DEN).overall

        assert overall.closed_tickets == 2
        assert overall.rating_count == 1
        assert overall.response_rate == 0.5

    def test_response_rate_la_None_khi_chua_co_ticket_dong_nao(self, db):
        rong_tu = datetime(2020, 1, 1, tzinfo=UTC)
        overall = SatisfactionService(db).report(rong_tu, rong_tu + timedelta(days=1)).overall

        # None = "chưa đủ dữ liệu", KHÁC 0 = "không ai đánh giá dù đã đóng nhiều ticket"
        assert overall.closed_tickets == 0
        assert overall.response_rate is None

    def test_response_rate_la_0_khi_dong_nhieu_nhung_khong_ai_danh_gia(
        self, db, make_user, agent_a
    ):
        nv = make_user()
        them_ticket_da_dong(db, nv, assignee=agent_a)
        them_ticket_da_dong(db, nv, assignee=agent_a)

        overall = SatisfactionService(db).report(TU, DEN).overall

        assert overall.closed_tickets == 2
        assert overall.rating_count == 0
        assert overall.response_rate == 0.0
        assert overall.avg_score is None


class TestTheoAgent:
    def test_tach_diem_theo_tung_agent(self, db, make_user, agent_a, agent_b):
        nv = make_user()
        ta = them_ticket_da_dong(db, nv, assignee=agent_a)
        tb = them_ticket_da_dong(db, nv, assignee=agent_b)
        them_danh_gia(db, ta, nv, score=5)
        them_danh_gia(db, tb, nv, score=2)

        theo_agent = {b.label: b for b in SatisfactionService(db).report(TU, DEN).by_agent}

        assert theo_agent["Agent A"].avg_score == 5.0
        assert theo_agent["Agent B"].avg_score == 2.0
        assert theo_agent["Agent A"].rating_count == 1
        assert theo_agent["Agent B"].rating_count == 1

    def test_agent_dong_nhieu_ticket_nhung_khong_duoc_danh_gia_van_xuat_hien(
        self, db, make_user, agent_a
    ):
        """Agent chưa có đánh giá nào vẫn phải có mặt trong báo cáo — nếu
        không, tỉ lệ phản hồi thấp của người đó sẽ vô hình đối với Admin."""
        nv = make_user()
        them_ticket_da_dong(db, nv, assignee=agent_a)
        them_ticket_da_dong(db, nv, assignee=agent_a)

        theo_agent = {b.label: b for b in SatisfactionService(db).report(TU, DEN).by_agent}

        assert "Agent A" in theo_agent
        bucket = theo_agent["Agent A"]
        assert bucket.rating_count == 0
        assert bucket.closed_tickets == 2
        assert bucket.response_rate == 0.0

    def test_giao_lai_ve_sau_khong_lam_doi_so_lieu_lich_su(self, db, make_user, agent_a, agent_b):
        """★ `ticket_ratings.agent_id` là bản SAO tại thời điểm đánh giá.

        Nếu ticket bị giao lại cho Agent B sau khi đã được Agent A xử lý và
        được đánh giá, điểm đó vẫn phải thuộc về Agent A trong báo cáo.
        """
        nv = make_user()
        ticket = them_ticket_da_dong(db, nv, assignee=agent_a)
        them_danh_gia(db, ticket, nv, score=5)

        # Giao lại ticket cho Agent B SAU khi đã đánh giá — không sửa lại bản ghi rating.
        ticket.assignee_id = agent_b.id
        db.flush()

        theo_agent = {b.label: b for b in SatisfactionService(db).report(TU, DEN).by_agent}

        assert theo_agent["Agent A"].rating_count == 1
        assert "Agent B" not in theo_agent or theo_agent["Agent B"].rating_count == 0


class TestTheoLoaiSuCo:
    def test_gom_theo_category(self, db, make_user, agent_a, ticket_category):
        nv = make_user()
        khac = TicketCategory(slug=f"khac-{uuid4().hex[:6]}", name="Loại khác")
        db.add(khac)
        db.flush()

        t1 = them_ticket_da_dong(db, nv, assignee=agent_a, category=ticket_category)
        t2 = them_ticket_da_dong(db, nv, assignee=agent_a, category=khac)
        them_danh_gia(db, t1, nv, score=5)
        them_danh_gia(db, t2, nv, score=1)

        theo_loai = {b.key: b for b in SatisfactionService(db).report(TU, DEN).by_category}

        assert theo_loai[ticket_category.slug].avg_score == 5.0
        assert theo_loai[khac.slug].avg_score == 1.0

    def test_ticket_chua_phan_loai_gom_vao_mot_dong_rieng(self, db, make_user, agent_a):
        nv = make_user()
        ticket = them_ticket_da_dong(db, nv, assignee=agent_a, category=None)
        them_danh_gia(db, ticket, nv, score=4)

        theo_loai = {b.key: b for b in SatisfactionService(db).report(TU, DEN).by_category}

        assert "unclassified" in theo_loai
        assert theo_loai["unclassified"].label == "Chưa phân loại"
        assert theo_loai["unclassified"].rating_count == 1


class TestTheoThang:
    def test_gom_theo_thang_dua_tren_thoi_diem_danh_gia(self, db, make_user, agent_a):
        nv = make_user()
        thang_7 = MOC
        thang_8 = MOC + timedelta(days=20)

        t1 = them_ticket_da_dong(db, nv, assignee=agent_a, xong_luc=thang_7)
        t2 = them_ticket_da_dong(db, nv, assignee=agent_a, xong_luc=thang_8)
        them_danh_gia(db, t1, nv, score=5, luc=thang_7)
        them_danh_gia(db, t2, nv, score=3, luc=thang_8)

        theo_thang = SatisfactionService(db).report(TU, DEN).by_month

        assert len(theo_thang) == 2
        thang_7_bucket = next(b for b in theo_thang if b.key == "2026-07-01")
        thang_8_bucket = next(b for b in theo_thang if b.key == "2026-08-01")
        assert thang_7_bucket.avg_score == 5.0
        assert thang_8_bucket.avg_score == 3.0

    def test_thang_sap_xep_tang_dan(self, db, make_user, agent_a):
        nv = make_user()
        for offset in (20, 0, 10):
            luc = MOC + timedelta(days=offset)
            ticket = them_ticket_da_dong(db, nv, assignee=agent_a, xong_luc=luc)
            them_danh_gia(db, ticket, nv, score=4, luc=luc)

        theo_thang = SatisfactionService(db).report(TU, DEN).by_month
        keys = [b.key for b in theo_thang]

        assert keys == sorted(keys)


class TestQuyenTruyCapHTTP:
    """Chỉ Admin gọi được `/reports/satisfaction` — cùng chính sách với
    US-37 → US-40 (xem ghi chú đầu `reports/router.py`)."""

    def test_admin_goi_thanh_cong(self, client, make_user, login):
        admin = make_user(role=UserRole.ADMIN)
        c = login(admin)

        r = c.get("/api/v1/reports/satisfaction")

        assert r.status_code == 200, r.text
        body = r.json()
        assert "overall" in body
        assert "byAgent" in body
        assert "byCategory" in body
        assert "byMonth" in body
        assert "responseRate" in body["overall"]

    def test_employee_bi_tu_choi(self, client, make_user, login):
        nv = make_user()
        c = login(nv)

        r = c.get("/api/v1/reports/satisfaction")

        assert r.status_code == 403

    def test_agent_bi_tu_choi(self, client, make_user, login):
        """US-42 viết \"Là Admin\" — Agent không có quyền xem báo cáo toàn hệ
        thống này, dù chính họ được chấm điểm trong đó (xem US-43 thay thế)."""
        agent = make_user(role=UserRole.IT_AGENT)
        c = login(agent)

        r = c.get("/api/v1/reports/satisfaction")

        assert r.status_code == 403

    def test_json_tra_ve_dung_hinh_dang(self, client, db, make_user, login, agent_a):
        admin = make_user(role=UserRole.ADMIN)
        nv = make_user()
        them_ticket_da_dong(db, nv, assignee=agent_a)

        c = login(admin)
        r = c.get("/api/v1/reports/satisfaction")

        assert r.status_code == 200, r.text
        body = r.json()
        for bucket in [body["overall"], *body["byAgent"], *body["byCategory"], *body["byMonth"]]:
            assert set(bucket["distribution"].keys()) <= {"1", "2", "3", "4", "5"}
            assert "ratingCount" in bucket
            assert "closedTickets" in bucket
