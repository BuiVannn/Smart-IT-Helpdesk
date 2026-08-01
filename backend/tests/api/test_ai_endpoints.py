"""Test API cho F3 — gợi ý người xử lý (US-20), sửa phân loại (US-21),
báo cáo độ chính xác (US-22).

Nhóm test về quyền là quan trọng nhất: gợi ý người xử lý làm lộ khối lượng
công việc của toàn đội IT, nhân viên thường không có việc gì phải thấy nó.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.tickets.constants import AiStatus, EventType, TicketPriority, TicketStatus
from app.modules.tickets.models import AiClassification, Ticket, TicketCategory, TicketEvent
from app.modules.users.constants import UserRole
from app.modules.users.models import AgentSkill

BASE = "/api/v1/tickets"
REPORTS = "/api/v1/reports"

TICKET_BODY = {
    "title": "Không kết nối được WiFi công ty tại tầng 5",
    "description": "Từ sáng nay máy tôi không thấy mạng CTY-WIFI, đã thử khởi động lại.",
}


@pytest.fixture
def categories(db) -> dict[str, TicketCategory]:
    wanted = [
        ("network", "Mạng & Internet", TicketPriority.HIGH),
        ("hardware", "Phần cứng & Thiết bị", TicketPriority.MEDIUM),
    ]
    result = {}
    for slug, name, priority in wanted:
        category = db.execute(
            select(TicketCategory).where(TicketCategory.slug == slug)
        ).scalar_one_or_none()
        if category is None:
            category = TicketCategory(slug=slug, name=name, default_priority=priority)
            db.add(category)
            db.flush()
        result[slug] = category
    return result


@pytest.fixture
def employee(make_user, sla_policies):
    return make_user(role=UserRole.EMPLOYEE, full_name="Nhân Viên Thường")


@pytest.fixture
def agent(make_user):
    user = make_user(role=UserRole.IT_AGENT, full_name="Chu Quang Vũ")
    user.last_login_at = datetime.now(UTC)
    return user


def as_user(client, login, user):
    client.headers.pop("Authorization", None)
    return login(user)


def make_ticket(db, requester, categories, **overrides) -> Ticket:
    """Tạo ticket qua service để có mã, hạn SLA và sự kiện đầy đủ."""
    from app.modules.tickets.schemas import CreateTicketRequest
    from app.modules.tickets.service import TicketService

    data = CreateTicketRequest.model_validate({**TICKET_BODY, **overrides})
    return TicketService(db).create(requester, data)


def apply_ai(db, ticket: Ticket, category: TicketCategory, *, confidence=0.92) -> AiClassification:
    """Giả lập worker đã phân loại xong và áp dụng kết quả."""
    ticket.category_id = category.id
    ticket.ai_status = AiStatus.APPLIED
    record = AiClassification(
        ticket_id=ticket.id,
        model_name="fake-model",
        prompt_version="classify-v1.0",
        suggested_category_id=category.id,
        suggested_priority=ticket.priority,
        confidence=confidence,
        reasoning="Mô tả nêu rõ không vào được WiFi",
        was_applied=True,
        latency_ms=1200,
        prompt_tokens=120,
        completion_tokens=25,
    )
    db.add(record)
    db.flush()
    return record


class TestQuyenXemGoiYNguoiXuLy:
    """US-20 — ma trận quyền ở docs/design/06 §4."""

    def test_nhan_vien_bi_tu_choi(self, client, login, db, employee, agent, categories):
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, employee)

        response = c.get(f"{BASE}/{ticket.id}/assignee-suggestions")

        assert response.status_code == 403

    def test_agent_xem_duoc(self, client, login, db, employee, agent, categories):
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, agent)

        response = c.get(f"{BASE}/{ticket.id}/assignee-suggestions")

        assert response.status_code == 200, response.text
        assert "suggestions" in response.json()

    def test_admin_xem_duoc(self, client, login, db, make_user, employee, categories):
        admin = make_user(role=UserRole.ADMIN)
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, admin)

        assert c.get(f"{BASE}/{ticket.id}/assignee-suggestions").status_code == 200

    def test_ticket_khong_ton_tai_tra_404(self, client, login, agent):
        from uuid import uuid4

        c = as_user(client, login, agent)

        assert c.get(f"{BASE}/{uuid4()}/assignee-suggestions").status_code == 404


class TestNoiDungGoiY:
    """US-20 — top 3 kèm điểm và lý do đọc được."""

    def test_toi_da_ba_ung_vien(self, client, login, db, make_user, employee, categories):
        for i in range(6):
            make_user(role=UserRole.IT_AGENT, full_name=f"Agent {i}")
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, make_user(role=UserRole.ADMIN))

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        assert len(body["suggestions"]) <= 3

    def test_moi_ung_vien_co_diem_va_ly_do(
        self, client, login, db, employee, agent, categories
    ):
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, agent)

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        assert body["suggestions"], "phải có ít nhất Agent vừa tạo"
        for item in body["suggestions"]:
            assert 0 <= item["score"] <= 1
            assert item["reason"]
            assert "agentId" in item and "fullName" in item

    def test_khong_lo_email_cua_dong_nghiep(
        self, client, login, db, employee, agent, categories
    ):
        """Cùng lý do với `UserBrief`: danh sách này không phải chỗ lộ email."""
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, agent)

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        for item in body["suggestions"]:
            assert "email" not in item

    def test_agent_co_chuyen_mon_xep_truoc(
        self, client, login, db, make_user, employee, categories
    ):
        chuyen_gia = make_user(role=UserRole.IT_AGENT, full_name="Chuyên Gia Mạng")
        make_user(role=UserRole.IT_AGENT, full_name="Người Mới")
        db.add(AgentSkill(
            agent_id=chuyen_gia.id, category_id=categories["network"].id, level=3
        ))
        db.flush()

        ticket = make_ticket(db, employee, categories, categoryId=str(categories["network"].id))
        c = as_user(client, login, make_user(role=UserRole.ADMIN))

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        assert body["suggestions"][0]["fullName"] == "Chuyên Gia Mạng"
        assert body["suggestions"][0]["skillLevel"] == 3
        assert "Mạng & Internet" in body["suggestions"][0]["reason"]

    def test_khong_goi_y_agent_da_bi_khoa(
        self, client, login, db, make_user, employee, agent, categories
    ):
        khoa = make_user(role=UserRole.IT_AGENT, full_name="Đã Nghỉ Việc", is_active=False)
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, agent)

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        assert str(khoa.id) not in [s["agentId"] for s in body["suggestions"]]

    def test_agent_ranh_co_tai_bang_khong(
        self, client, login, db, employee, agent, categories
    ):
        """★ LEFT JOIN không khớp dòng nào ⇒ mọi cột ticket là NULL.

        Nếu biểu thức tính tải không loại trừ trường hợp đó, Agent đang rảnh
        bị tính tải 1 — giao diện hiện "đang rảnh" ngay cạnh "tải 1", và mọi
        Agent rảnh đều bị trừ điểm y như nhau nên xếp hạng mất ý nghĩa.
        """
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, agent)

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        mine = next(s for s in body["suggestions"] if s["agentId"] == str(agent.id))
        assert mine["openTickets"] == 0
        assert mine["weightedLoad"] == 0

    def test_khong_goi_y_nhan_vien_thuong(
        self, client, login, db, employee, agent, categories
    ):
        """BR-02: giao cho nhân viên thường nghĩa là ticket rơi vào hố đen."""
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, agent)

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        assert str(employee.id) not in [s["agentId"] for s in body["suggestions"]]

    def test_tai_khong_bi_nhan_len_khi_agent_co_nhieu_ky_nang(
        self, client, login, db, make_user, employee, agent, categories
    ):
        """★ Ticket chưa phân loại + Agent có nhiều kỹ năng = bẫy nhân bản dòng.

        Nếu join `agent_skills` chỉ theo `agent_id`, mỗi kỹ năng sinh thêm một
        dòng và `count(tickets)` bị nhân lên đúng bằng số kỹ năng.
        """
        for category in categories.values():
            db.add(AgentSkill(agent_id=agent.id, category_id=category.id, level=2))
        db.flush()

        giao_cho_agent = make_ticket(db, employee, categories)
        giao_cho_agent.assignee_id = agent.id
        giao_cho_agent.status = TicketStatus.ASSIGNED
        db.flush()

        ticket = make_ticket(db, employee, categories)   # chưa phân loại
        c = as_user(client, login, make_user(role=UserRole.ADMIN))

        body = c.get(f"{BASE}/{ticket.id}/assignee-suggestions").json()

        mine = next(s for s in body["suggestions"] if s["agentId"] == str(agent.id))
        assert mine["openTickets"] == 1, "một ticket phải được đếm đúng một lần"


class TestXemGoiYPhanLoaiCuaAi:
    """US-19 — giao diện cần thấy AI nghĩ gì, kể cả khi AI không tự áp dụng."""

    def test_tra_null_khi_ai_chua_chay(self, client, login, db, employee, categories):
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, employee)

        response = c.get(f"{BASE}/{ticket.id}/ai-classification")

        assert response.status_code == 200
        assert response.json() is None

    def test_tra_goi_y_sau_khi_phan_loai(self, client, login, db, employee, categories):
        ticket = make_ticket(db, employee, categories)
        apply_ai(db, ticket, categories["network"])
        c = as_user(client, login, employee)

        body = c.get(f"{BASE}/{ticket.id}/ai-classification").json()

        assert body["wasApplied"] is True
        assert body["confidence"] == pytest.approx(0.92)
        assert body["suggestedCategory"]["slug"] == "network"
        assert body["modelName"] == "fake-model"
        assert body["promptVersion"] == "classify-v1.0"

    def test_nhan_vien_khong_xem_duoc_ticket_nguoi_khac(
        self, client, login, db, make_user, employee, categories
    ):
        """404 chứ không phải 403 — xem docs/design/06 §4."""
        nguoi_khac = make_user(role=UserRole.EMPLOYEE)
        ticket = make_ticket(db, employee, categories)
        c = as_user(client, login, nguoi_khac)

        assert c.get(f"{BASE}/{ticket.id}/ai-classification").status_code == 404


class TestAgentSuaPhanLoaiCuaAi:
    """US-21 — sửa lại category để dữ liệu đúng VÀ để AI được đo lường."""

    def test_danh_dau_was_accepted_false_va_luu_loai_da_sua(
        self, client, login, db, employee, agent, categories
    ):
        ticket = make_ticket(db, employee, categories)
        record = apply_ai(db, ticket, categories["network"])
        c = as_user(client, login, agent)

        response = c.patch(
            f"{BASE}/{ticket.id}",
            json={"categoryId": str(categories["hardware"].id), "version": ticket.version},
        )

        assert response.status_code == 200, response.text
        db.refresh(record)
        assert record.was_accepted is False
        assert record.corrected_category_id == categories["hardware"].id
        assert record.corrected_at is not None

    def test_ghi_su_kien_reclassified(
        self, client, login, db, employee, agent, categories
    ):
        ticket = make_ticket(db, employee, categories)
        apply_ai(db, ticket, categories["network"])
        c = as_user(client, login, agent)

        c.patch(
            f"{BASE}/{ticket.id}",
            json={"categoryId": str(categories["hardware"].id), "version": ticket.version},
        )

        events = db.execute(
            select(TicketEvent).where(
                TicketEvent.ticket_id == ticket.id,
                TicketEvent.event_type == EventType.RECLASSIFIED,
            )
        ).scalars().all()
        assert len(events) == 1
        assert events[0].actor_id == agent.id

    def test_sua_di_sua_lai_dung_loai_ai_chon_thi_hoan_tac(
        self, client, login, db, employee, agent, categories
    ):
        """Thao tác nhầm rồi sửa lại không được vĩnh viễn tính là "AI sai"."""
        ticket = make_ticket(db, employee, categories)
        record = apply_ai(db, ticket, categories["network"])
        c = as_user(client, login, agent)

        c.patch(f"{BASE}/{ticket.id}", json={
            "categoryId": str(categories["hardware"].id), "version": ticket.version
        })
        db.refresh(ticket)
        c.patch(f"{BASE}/{ticket.id}", json={
            "categoryId": str(categories["network"].id), "version": ticket.version
        })

        db.refresh(record)
        assert record.was_accepted is None
        assert record.corrected_at is None

    def test_khong_tinh_la_sai_khi_ai_chua_tung_ap_dung(
        self, client, login, db, employee, agent, categories
    ):
        """★ Ticket AI không áp dụng (độ tin cậy thấp) mà Agent tự phân loại
        thì KHÔNG được tính vào mẫu số "AI sai" — nếu tính, tỉ lệ chính xác ở
        US-22 sẽ thấp hơn sự thật một cách có hệ thống.
        """
        ticket = make_ticket(db, employee, categories)
        record = AiClassification(
            ticket_id=ticket.id, model_name="fake-model", prompt_version="classify-v1.0",
            suggested_category_id=categories["network"].id, confidence=0.4,
            reasoning="Không chắc", was_applied=False,
        )
        db.add(record)
        ticket.ai_status = AiStatus.LOW_CONFIDENCE
        db.flush()
        c = as_user(client, login, agent)

        c.patch(f"{BASE}/{ticket.id}", json={
            "categoryId": str(categories["hardware"].id), "version": ticket.version
        })

        db.refresh(record)
        assert record.was_accepted is None

    def test_dong_ticket_ma_khong_ai_sua_thi_tinh_la_chap_nhan(
        self, client, login, db, employee, agent, categories
    ):
        ticket = make_ticket(db, employee, categories)
        record = apply_ai(db, ticket, categories["network"])
        db.flush()

        c = as_user(client, login, agent)
        c.post(f"{BASE}/{ticket.id}/claim", json={"version": ticket.version})
        db.refresh(ticket)
        c.post(f"{BASE}/{ticket.id}/status",
               json={"status": TicketStatus.IN_PROGRESS, "version": ticket.version})
        db.refresh(ticket)
        c.post(f"{BASE}/{ticket.id}/status", json={
            "status": TicketStatus.RESOLVED,
            "resolutionNote": "Đã cấu hình lại access point tầng 5",
            "version": ticket.version,
        })
        db.refresh(ticket)
        response = c.post(f"{BASE}/{ticket.id}/status",
                          json={"status": TicketStatus.CLOSED, "version": ticket.version})

        assert response.status_code == 200, response.text
        db.refresh(record)
        assert record.was_accepted is True


class TestBaoCaoDoChinhXacAi:
    """US-22."""

    def test_nhan_vien_bi_tu_choi(self, client, login, employee):
        c = as_user(client, login, employee)

        assert c.get(f"{REPORTS}/ai-accuracy").status_code == 403

    def test_agent_xem_duoc(self, client, login, agent):
        c = as_user(client, login, agent)

        assert c.get(f"{REPORTS}/ai-accuracy").status_code == 200

    def test_chua_co_du_lieu_thi_ti_le_la_null_khong_phai_0(self, client, login, agent):
        """★ 0 nghĩa là "AI sai tất"; null nghĩa là "chưa đủ dữ liệu".

        Báo cáo tuần đầu luôn rơi vào vế sau, và hiển thị 0% ở đó sẽ khiến cả
        nhóm kết luận sai về chất lượng mô hình.
        """
        c = as_user(client, login, agent)
        tomorrow = datetime.now(UTC) + timedelta(days=1)

        body = c.get(f"{REPORTS}/ai-accuracy", params={
            "from": tomorrow.isoformat(), "to": (tomorrow + timedelta(days=1)).isoformat()
        }).json()

        assert body["totalRuns"] == 0
        assert body["acceptanceRate"] is None

    def test_tinh_ti_le_chap_nhan(
        self, client, login, db, employee, agent, categories
    ):
        for accepted in (True, True, True, False):
            ticket = make_ticket(db, employee, categories)
            record = apply_ai(db, ticket, categories["network"])
            record.was_accepted = accepted
        db.flush()
        c = as_user(client, login, agent)

        body = c.get(f"{REPORTS}/ai-accuracy").json()

        assert body["accepted"] >= 3
        assert body["corrected"] >= 1
        assert body["acceptanceRate"] is not None
        assert 0 <= body["acceptanceRate"] <= 1

    def test_co_du_cac_muc_theo_ac(self, client, login, db, employee, agent, categories):
        ticket = make_ticket(db, employee, categories)
        record = apply_ai(db, ticket, categories["network"])
        record.was_accepted = False
        db.flush()
        c = as_user(client, login, agent)

        body = c.get(f"{REPORTS}/ai-accuracy").json()

        assert "byCategory" in body and body["byCategory"]
        assert "byWeek" in body and body["byWeek"]
        assert "confusion" in body
        assert "statusBreakdown" in body
        assert body["avgLatencyMs"] is not None
        assert body["estimatedCostUsd"] >= 0
        assert body["generatedAt"]

    def test_ma_tran_nham_lan_doi_chieu_loai_cuoi_cung(
        self, client, login, db, employee, agent, categories
    ):
        ticket = make_ticket(db, employee, categories)
        apply_ai(db, ticket, categories["network"])
        ticket.category_id = categories["hardware"].id   # Agent đã sửa lại
        db.flush()
        c = as_user(client, login, agent)

        body = c.get(f"{REPORTS}/ai-accuracy").json()

        cells = {(c_["aiCategory"], c_["finalCategory"]) for c_ in body["confusion"]}
        assert ("Mạng & Internet", "Phần cứng & Thiết bị") in cells
