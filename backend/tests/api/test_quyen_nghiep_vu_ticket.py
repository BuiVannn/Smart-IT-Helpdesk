"""Ai được làm gì với ticket — ba quy tắc nghiệp vụ đã từng bị hở (P0-5, 7, 8).

Cả ba đều là lỗi "chạy được nhưng sai nghiệp vụ": không endpoint nào lỗi,
không dữ liệu nào hỏng về mặt kỹ thuật, nhưng người không đủ thẩm quyền thực
hiện được hành động không hoàn tác, và người dùng tự sửa được thứ thuộc quyền
quyết định của đội IT.
"""

from app.modules.tickets.constants import TicketStatus
from app.modules.users.constants import UserRole

MO_TA = "Mô tả đủ dài để qua ràng buộc CHECK của bảng tickets."


def tao_ticket(client, tieu_de="Sự cố cần kiểm chứng quyền hạn"):
    r = client.post("/api/v1/tickets", json={"title": tieu_de, "description": MO_TA})
    assert r.status_code == 201, r.text
    return r.json()


def dua_toi_resolved(client_agent, ticket_id, version):
    """Đưa ticket qua chuỗi nhận việc → xử lý → đã xử lý xong."""
    r = client_agent.post(f"/api/v1/tickets/{ticket_id}/claim", json={"version": version})
    version = r.json()["version"]
    r = client_agent.post(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS", "version": version},
    )
    version = r.json()["version"]
    r = client_agent.post(
        f"/api/v1/tickets/{ticket_id}/status",
        json={
            "status": "RESOLVED",
            "version": version,
            "resolutionNote": "Đã thay thiết bị và kiểm tra lại",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["version"]


class TestP07AiDuocDongTicket:
    """`RESOLVED → CLOSED` — tài liệu 03 §5: Requester, Hệ thống, Admin."""

    def test_agent_KHONG_dong_duoc_ticket_cua_nguoi_khac(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """★ Đóng ticket là hành động KHÔNG HOÀN TÁC ĐƯỢC: `CLOSED` là trạng
        thái cuối, nên đóng sớm tước vĩnh viễn cửa sổ mở lại 7 ngày của người
        yêu cầu và chốt sổ "AI phân loại đúng" cho US-22.

        Bản trước để ô này là ALL_ROLES trần — một Agent bất kỳ, không phải
        người xử lý, không phải người yêu cầu, đóng được và nhận HTTP 200.
        """
        nhan_vien = make_user()
        agent_xu_ly = make_user(role=UserRole.IT_AGENT)
        agent_ngoai_cuoc = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))
        version = dua_toi_resolved(login(agent_xu_ly), ticket["id"], ticket["version"])

        c = login(agent_ngoai_cuoc)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "CLOSED", "version": version},
        )

        assert r.status_code == 422
        assert "người tạo ticket" in r.json()["error"]["message"]

    def test_nguoi_yeu_cau_dong_duoc(self, client, make_user, login, sla_policies, ticket_category):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))
        version = dua_toi_resolved(login(agent), ticket["id"], ticket["version"])

        c = login(nhan_vien)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "CLOSED", "version": version},
        )

        assert r.status_code == 200
        assert r.json()["status"] == TicketStatus.CLOSED

    def test_admin_van_dong_duoc(self, client, make_user, login, sla_policies, ticket_category):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)

        ticket = tao_ticket(login(nhan_vien))
        version = dua_toi_resolved(login(agent), ticket["id"], ticket["version"])

        c = login(admin)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "CLOSED", "version": version},
        )

        assert r.status_code == 200


class TestP07AgentTuTaoTicketChoMinh:
    """Cờ `requester_only` đã giới hạn đúng người rồi; liệt kê thêm bộ vai trò
    chỉ tạo ra một điều kiện thứ hai SAI."""

    def test_IT_AGENT_huy_duoc_ticket_do_chinh_minh_tao(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """Agent tạo ticket cho chính mình là việc hoàn toàn hợp lệ — không có
        gì chặn. Bản trước liệt kê `{EMPLOYEE, ADMIN}` nên Agent bị kẹt: không
        huỷ được ticket tạo nhầm, cũng không mở lại được."""
        agent = make_user(role=UserRole.IT_AGENT)
        c = login(agent)
        ticket = tao_ticket(c, "Ticket do chính Agent tự tạo")

        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "CANCELLED", "version": ticket["version"]},
        )

        assert r.status_code == 200, r.text
        assert r.json()["status"] == TicketStatus.CANCELLED

    def test_nguoi_ngoai_van_KHONG_huy_duoc(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        ke_khac = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))

        c = login(ke_khac)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "CANCELLED", "version": ticket["version"]},
        )

        assert r.status_code == 422


class TestP07KeoLaiTicketDangChoNguoiDung:
    """`PENDING_REQUESTER → IN_PROGRESS` — tài liệu 03 §5: Assignee, Requester."""

    def test_agent_ngoai_cuoc_KHONG_keo_lai_duoc(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent_xu_ly = make_user(role=UserRole.IT_AGENT)
        agent_ngoai_cuoc = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))
        c = login(agent_xu_ly)
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/claim", json={"version": ticket["version"]}
        ).json()["version"]
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/status", json={"status": "IN_PROGRESS", "version": v}
        ).json()["version"]
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "PENDING_REQUESTER", "version": v},
        ).json()["version"]

        c = login(agent_ngoai_cuoc)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "IN_PROGRESS", "version": v},
        )

        assert r.status_code == 422

    def test_nguoi_yeu_cau_phan_hoi_thi_di_tiep_duoc(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))
        c = login(agent)
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/claim", json={"version": ticket["version"]}
        ).json()["version"]
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/status", json={"status": "IN_PROGRESS", "version": v}
        ).json()["version"]
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "PENDING_REQUESTER", "version": v},
        ).json()["version"]

        c = login(nhan_vien)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "IN_PROGRESS", "version": v},
        )

        assert r.status_code == 200, r.text


class TestP08NhanVienKhongTuNangMucUuTien:
    def test_nhan_vien_KHONG_doi_duoc_muc_uu_tien_ticket_cua_minh(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """★ Hậu quả kép nếu để lọt: `_apply_sla` tính lại hạn theo URGENT nên
        người đó nhảy lên đầu hàng chờ, và mọi chỉ số vi phạm SLA mất ý nghĩa
        vì mức ưu tiên không còn do đội IT đánh giá."""
        nhan_vien = make_user()
        c = login(nhan_vien)
        ticket = tao_ticket(c)

        r = c.patch(
            f"/api/v1/tickets/{ticket['id']}",
            json={"priority": "URGENT", "version": ticket["version"]},
        )

        assert r.status_code == 403
        assert r.json()["error"]["details"]["editableFields"] == ["title", "description"]

    def test_nhan_vien_KHONG_doi_duoc_loai_su_co(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """Sửa `categoryId` còn kích hoạt `_record_ai_correction`, tức người
        dùng TỰ ĐÁNH DẤU AI phân loại sai và bóp méo báo cáo US-22."""
        nhan_vien = make_user()
        c = login(nhan_vien)
        ticket = tao_ticket(c)

        r = c.patch(
            f"/api/v1/tickets/{ticket['id']}",
            json={"categoryId": str(ticket_category.id), "version": ticket["version"]},
        )

        assert r.status_code == 403

    def test_nhan_vien_VAN_sua_duoc_tieu_de_va_mo_ta(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        c = login(nhan_vien)
        ticket = tao_ticket(c)

        r = c.patch(
            f"/api/v1/tickets/{ticket['id']}",
            json={"title": "Tiêu đề đã được sửa lại cho rõ", "version": ticket["version"]},
        )

        assert r.status_code == 200
        assert r.json()["title"] == "Tiêu đề đã được sửa lại cho rõ"

    def test_agent_VAN_doi_duoc_muc_uu_tien(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """Đây mới là người có thẩm quyền đánh giá tác động."""
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        ticket = tao_ticket(login(nhan_vien))

        c = login(agent)
        r = c.patch(
            f"/api/v1/tickets/{ticket['id']}",
            json={"priority": "URGENT", "version": ticket["version"]},
        )

        assert r.status_code == 200
        assert r.json()["priority"] == "URGENT"


class TestNutHienThiDungVoiTungNguoi:
    def test_allowed_transitions_khong_hien_nut_nguoi_do_khong_bam_duoc(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """Endpoint này sinh ra để giao diện CHỈ hiện nút hợp lệ. Nếu nó lọc
        theo vai trò mà bỏ qua "có phải người tạo không", giao diện sẽ hiện
        nút "Huỷ" cho mọi Agent rồi để backend từ chối — đúng cái nó phải tránh.
        """
        nhan_vien = make_user()
        agent_ngoai_cuoc = make_user(role=UserRole.IT_AGENT)
        ticket = tao_ticket(login(nhan_vien))

        cua_nguoi_tao = (
            login(nhan_vien)
            .get(f"/api/v1/tickets/{ticket['id']}/allowed-transitions")
            .json()["allowedStatuses"]
        )
        cua_nguoi_ngoai = (
            login(agent_ngoai_cuoc)
            .get(f"/api/v1/tickets/{ticket['id']}/allowed-transitions")
            .json()["allowedStatuses"]
        )

        assert TicketStatus.CANCELLED in cua_nguoi_tao
        assert TicketStatus.CANCELLED not in cua_nguoi_ngoai
