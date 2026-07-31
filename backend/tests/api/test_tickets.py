"""Test API ticket — US-08 → US-18.

Nhóm test quan trọng nhất là TestCachLy: nhân viên đọc được ticket của người
khác là rủi ro nghiêm trọng nhất của hệ thống này.
"""

import re

import pytest

from app.modules.tickets.constants import TicketStatus
from app.modules.users.constants import UserRole

BASE = "/api/v1/tickets"

TICKET_BODY = {
    "title": "Không kết nối được WiFi công ty tại tầng 5",
    "description": "Từ sáng nay máy tôi không thấy mạng CTY-WIFI, đã thử khởi động lại.",
}


@pytest.fixture
def employee_client(client, make_user, login, sla_policies):
    user = make_user(role=UserRole.EMPLOYEE)
    login(user)
    client.current_user = user
    return client


def create_ticket(c, **overrides) -> dict:
    body = {**TICKET_BODY, **overrides}
    response = c.post(BASE, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def as_user(client, login, user):
    """Đổi danh tính trên cùng một client."""
    client.headers.pop("Authorization", None)
    login(user)
    return client


class TestTaoTicket:
    """US-08 — Tạo ticket."""

    def test_tao_thanh_cong(self, employee_client):
        body = create_ticket(employee_client)

        assert body["status"] == TicketStatus.NEW
        assert body["assignee"] is None
        assert body["version"] == 1

    def test_ma_ticket_dung_dinh_dang(self, employee_client):
        body = create_ticket(employee_client)
        assert re.fullmatch(r"HD-\d{6}-\d{5}", body["code"]), body["code"]

    def test_ma_ticket_khong_trung_nhau(self, employee_client):
        """Sinh mã bằng SEQUENCE chứ không phải max+1 — max+1 cấp trùng khi
        hai người tạo cùng lúc, và mã trùng thì không sửa lại được."""
        codes = {create_ticket(employee_client)["code"] for _ in range(5)}
        assert len(codes) == 5

    def test_ai_status_la_PENDING_de_phan_loai_chay_nen(self, employee_client):
        """API phải trả về ngay, không chờ LLM. Nếu AI hỏng, ticket vẫn dùng được."""
        assert create_ticket(employee_client)["aiStatus"] == "PENDING"

    def test_han_SLA_duoc_tinh_luc_tao(self, employee_client):
        body = create_ticket(employee_client)
        assert body["slaResolutionDueAt"] is not None
        assert body["slaResponseDueAt"] is not None

    def test_muc_uu_tien_lay_theo_loai_su_co(self, employee_client, ticket_category):
        """Loại "Mạng" mặc định HIGH — không phải hằng số MEDIUM cứng trong code."""
        body = create_ticket(employee_client, categoryId=str(ticket_category.id))
        assert body["priority"] == "HIGH"

    def test_tieu_de_qua_ngan_bi_tu_choi(self, employee_client):
        response = employee_client.post(BASE, json={**TICKET_BODY, "title": "wifi"})
        assert response.status_code == 422

    def test_chua_dang_nhap_thi_401(self, client):
        assert client.post(BASE, json=TICKET_BODY).status_code == 401


class TestCachLy:
    """★ NHÓM TEST QUAN TRỌNG NHẤT — nhân viên không được thấy ticket người khác."""

    def test_nhan_vien_chi_thay_ticket_cua_minh(
        self, client, make_user, login, sla_policies
    ):
        a, b = make_user(), make_user()

        as_user(client, login, a)
        create_ticket(client)

        as_user(client, login, b)
        body = client.get(BASE).json()

        assert body["pagination"]["totalItems"] == 0, (
            "totalItems phải lọc theo quyền — nếu không là lộ tổng số ticket toàn công ty"
        )
        assert body["data"] == []

    def test_xem_ticket_nguoi_khac_tra_404_KHONG_phai_403(
        self, client, make_user, login, sla_policies
    ):
        """403 là tự xác nhận "ticket này có tồn tại", cho phép dò mã ticket."""
        a, b = make_user(), make_user()

        as_user(client, login, a)
        ticket = create_ticket(client)

        as_user(client, login, b)
        assert client.get(f"{BASE}/{ticket['id']}").status_code == 404

    def test_agent_thay_moi_ticket(self, client, make_user, login, sla_policies):
        employee = make_user()
        as_user(client, login, employee)
        ticket = create_ticket(client)

        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        assert client.get(f"{BASE}/{ticket['id']}").status_code == 200

    def test_nhan_vien_khong_xem_duoc_hang_cho(self, employee_client):
        assert employee_client.get(f"{BASE}/stats/queue").status_code == 403

    def test_agent_xem_duoc_hang_cho(self, client, make_user, login, sla_policies):
        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        body = client.get(f"{BASE}/stats/queue").json()
        assert set(body) == {
            "unassigned", "assignedToMe", "inProgress", "atRisk", "breached"
        }


class TestGiaoViec:
    """US-13 — Nhận việc / giao việc."""

    def test_agent_tu_nhan_ticket(self, client, make_user, login, sla_policies):
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        agent = make_user(role=UserRole.IT_AGENT)
        as_user(client, login, agent)
        response = client.post(
            f"{BASE}/{ticket['id']}/claim", json={"version": ticket["version"]}
        )

        assert response.status_code == 200
        assert response.json()["status"] == TicketStatus.ASSIGNED
        assert response.json()["assignee"]["id"] == str(agent.id)

    def test_hai_agent_cung_nhan_thi_nguoi_sau_bi_tu_choi(
        self, client, make_user, login, sla_policies
    ):
        """★ Đây chính là tình huống khoá lạc quan bảo vệ. Không có nó thì
        người thứ hai âm thầm ghi đè người thứ nhất và không ai biết."""
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        assert client.post(
            f"{BASE}/{ticket['id']}/claim", json={"version": 1}
        ).status_code == 200

        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        response = client.post(f"{BASE}/{ticket['id']}/claim", json={"version": 1})

        assert response.status_code == 409
        assert response.json()["error"]["details"]["currentVersion"] == 2

    def test_khong_giao_duoc_cho_nguoi_khong_phai_agent(
        self, client, make_user, login, sla_policies
    ):
        """BR-02: giao cho nhân viên thường nghĩa là ticket rơi vào hố đen."""
        employee = make_user()
        as_user(client, login, employee)
        ticket = create_ticket(client)

        as_user(client, login, make_user(role=UserRole.ADMIN))
        response = client.post(
            f"{BASE}/{ticket['id']}/assign",
            json={"assigneeId": str(employee.id), "version": 1},
        )
        assert response.status_code == 422

    def test_nhan_vien_khong_duoc_giao_viec(self, client, make_user, login, sla_policies):
        agent = make_user(role=UserRole.IT_AGENT)
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        response = client.post(
            f"{BASE}/{ticket['id']}/assign",
            json={"assigneeId": str(agent.id), "version": 1},
        )
        assert response.status_code == 403

    def test_giao_lai_cho_agent_khac(self, client, make_user, login, sla_policies):
        """ASSIGNED → ASSIGNED là bước tự chuyển hợp lệ trong bảng trạng thái."""
        agent1 = make_user(role=UserRole.IT_AGENT)
        agent2 = make_user(role=UserRole.IT_AGENT)
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        as_user(client, login, agent1)
        claimed = client.post(f"{BASE}/{ticket['id']}/claim", json={"version": 1}).json()

        response = client.post(
            f"{BASE}/{ticket['id']}/assign",
            json={"assigneeId": str(agent2.id), "version": claimed["version"]},
        )
        assert response.status_code == 200
        assert response.json()["assignee"]["id"] == str(agent2.id)


class TestChuyenTrangThai:
    """US-14, US-18 — Vòng đời ticket."""

    @pytest.fixture
    def in_progress(self, client, make_user, login, sla_policies):
        """Ticket đã được agent nhận và bắt đầu xử lý."""
        agent = make_user(role=UserRole.IT_AGENT)
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        as_user(client, login, agent)
        claimed = client.post(f"{BASE}/{ticket['id']}/claim", json={"version": 1}).json()
        started = client.post(
            f"{BASE}/{ticket['id']}/status",
            json={"status": "IN_PROGRESS", "version": claimed["version"]},
        ).json()
        return started

    def test_buoc_chuyen_khong_hop_le_bi_tu_choi_kem_goi_y(
        self, client, make_user, login, sla_policies
    ):
        """Thông điệp lỗi phải kèm danh sách trạng thái hợp lệ, để frontend
        hướng dẫn được người dùng chứ không chỉ báo "không hợp lệ"."""
        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        ticket = create_ticket(client)

        response = client.post(
            f"{BASE}/{ticket['id']}/status", json={"status": "RESOLVED", "version": 1}
        )

        assert response.status_code == 422
        details = response.json()["error"]["details"]
        assert details["currentStatus"] == "NEW"
        assert "ASSIGNED" in details["allowedStatuses"]

    def test_xu_ly_xong_phai_co_ghi_chu(self, client, in_progress):
        response = client.post(
            f"{BASE}/{in_progress['id']}/status",
            json={"status": "RESOLVED", "version": in_progress["version"]},
        )
        assert response.status_code == 422

    def test_xu_ly_xong_ghi_lai_moc_thoi_gian(self, client, in_progress):
        response = client.post(
            f"{BASE}/{in_progress['id']}/status",
            json={
                "status": "RESOLVED",
                "resolutionNote": "Đã reset lại cấu hình DHCP trên switch tầng 5.",
                "version": in_progress["version"],
            },
        )

        assert response.status_code == 200
        assert response.json()["resolvedAt"] is not None
        assert response.json()["slaState"] in ("MET", "BREACHED")

    def test_sai_version_thi_409(self, client, in_progress):
        response = client.post(
            f"{BASE}/{in_progress['id']}/status",
            json={"status": "PENDING_REQUESTER", "version": 99},
        )
        assert response.status_code == 409

    def test_nguoi_tao_huy_duoc_ticket_cua_minh(
        self, client, make_user, login, sla_policies
    ):
        """US-18 — huỷ khi ticket còn ở NEW."""
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        response = client.post(
            f"{BASE}/{ticket['id']}/status", json={"status": "CANCELLED", "version": 1}
        )
        assert response.status_code == 200
        assert response.json()["status"] == TicketStatus.CANCELLED

    def test_allowed_transitions_theo_dung_vai_tro(
        self, client, make_user, login, sla_policies
    ):
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        body = client.get(f"{BASE}/{ticket['id']}/allowed-transitions").json()
        assert body["currentStatus"] == "NEW"
        # Nhân viên chỉ được huỷ, KHÔNG được tự gán người xử lý
        assert body["allowedStatuses"] == ["CANCELLED"]


class TestBinhLuan:
    """US-15 — Bình luận, và ranh giới bình luận nội bộ."""

    def test_nguoi_tao_binh_luan_duoc(self, employee_client):
        ticket = create_ticket(employee_client)
        response = employee_client.post(
            f"{BASE}/{ticket['id']}/comments", json={"body": "Vẫn chưa vào được ạ."}
        )
        assert response.status_code == 201
        assert response.json()["isInternal"] is False

    def test_nhan_vien_gui_isInternal_true_thi_BI_BO_QUA(self, employee_client):
        """★ Bỏ qua chứ KHÔNG báo lỗi (BR-10) — báo lỗi là tự khai với nhân
        viên rằng có tồn tại loại bình luận nội bộ."""
        ticket = create_ticket(employee_client)
        response = employee_client.post(
            f"{BASE}/{ticket['id']}/comments",
            json={"body": "Thử leo thang", "isInternal": True},
        )

        assert response.status_code == 201
        assert response.json()["isInternal"] is False

    def test_nhan_vien_KHONG_thay_binh_luan_noi_bo_cua_IT(
        self, client, make_user, login, sla_policies
    ):
        employee = make_user()
        as_user(client, login, employee)
        ticket = create_ticket(client)

        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        client.post(
            f"{BASE}/{ticket['id']}/comments",
            json={"body": "Máy này hết hạn bảo hành, đừng nói với user", "isInternal": True},
        )
        assert len(client.get(f"{BASE}/{ticket['id']}/comments").json()) == 1

        as_user(client, login, employee)
        comments = client.get(f"{BASE}/{ticket['id']}/comments").json()
        assert comments == [], "bình luận nội bộ bị lộ cho nhân viên"

    def test_khong_binh_luan_duoc_tren_ticket_nguoi_khac(
        self, client, make_user, login, sla_policies
    ):
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        as_user(client, login, make_user())
        response = client.post(
            f"{BASE}/{ticket['id']}/comments", json={"body": "Tôi xem trộm"}
        )
        assert response.status_code == 404


class TestTimKiemVaLichSu:
    """US-16, US-17."""

    def test_tim_kiem_khong_dau_van_ra_ket_qua(self, employee_client):
        """Người Việt gõ "mat khau" phải tìm ra "mật khẩu" — nếu không, chức
        năng tìm kiếm coi như không dùng được."""
        create_ticket(
            employee_client,
            title="Quên mật khẩu đăng nhập máy tính",
            description="Tôi không đăng nhập được vào máy tính từ sáng nay.",
        )

        body = employee_client.get(BASE, params={"q": "mat khau"}).json()
        assert body["pagination"]["totalItems"] == 1

    def test_tim_kiem_khong_vuot_qua_pham_vi_quyen(
        self, client, make_user, login, sla_policies
    ):
        as_user(client, login, make_user())
        create_ticket(client, title="Quên mật khẩu đăng nhập máy tính")

        as_user(client, login, make_user())
        body = client.get(BASE, params={"q": "mat khau"}).json()
        assert body["pagination"]["totalItems"] == 0

    def test_lich_su_ghi_lai_moi_thay_doi(self, client, make_user, login, sla_policies):
        as_user(client, login, make_user())
        ticket = create_ticket(client)

        as_user(client, login, make_user(role=UserRole.IT_AGENT))
        client.post(f"{BASE}/{ticket['id']}/claim", json={"version": 1})

        events = client.get(f"{BASE}/{ticket['id']}/events").json()
        types = [e["eventType"] for e in events]
        assert types[0] == "CREATED"
        assert "ASSIGNED" in types
        assert "STATUS_CHANGED" in types

    def test_phan_trang_hoat_dong(self, employee_client):
        for i in range(3):
            create_ticket(employee_client, title=f"Sự cố số {i} cần hỗ trợ gấp")

        body = employee_client.get(BASE, params={"pageSize": 2}).json()
        assert len(body["data"]) == 2
        assert body["pagination"]["totalItems"] == 3
        assert body["pagination"]["totalPages"] == 2
