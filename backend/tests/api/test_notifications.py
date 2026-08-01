"""API thông báo (F6 — US-33, US-34, US-36).

Test ở đây bám vào HÀNH VI NGƯỜI DÙNG THẤY: giao việc thì người được giao có
thông báo, người giao thì không; ai cũng chỉ thấy thông báo của mình.
"""

from app.modules.users.constants import UserRole


def tao_ticket(client, tieu_de="Máy in tầng 3 kẹt giấy liên tục"):
    response = client.post(
        "/api/v1/tickets",
        json={"title": tieu_de, "description": "Kẹt giấy mỗi lần in quá 5 trang, đã thử tắt bật."},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestUS34GiaoViecThiCoThongBao:
    def test_nguoi_duoc_giao_nhan_duoc_thong_bao(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT, full_name="Agent Một")
        admin = make_user(role=UserRole.ADMIN)

        ticket = tao_ticket(login(nhan_vien))

        c = login(admin)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            json={"assigneeId": str(agent.id), "version": ticket["version"]},
        )
        assert r.status_code == 200, r.text

        c = login(agent)
        assert c.get("/api/v1/notifications/unread-count").json()["count"] == 1

        items = c.get("/api/v1/notifications").json()["data"]
        assert items[0]["type"] == "TICKET_ASSIGNED"
        assert ticket["code"] in items[0]["title"]
        # entityType + entityId là thứ frontend dùng để điều hướng
        assert items[0]["entityType"] == "ticket"
        assert items[0]["entityId"] == ticket["id"]
        assert items[0]["isRead"] is False

    def test_BR18_agent_tu_nhan_viec_thi_KHONG_tu_bao_cho_minh(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))

        c = login(agent)
        r = c.post(f"/api/v1/tickets/{ticket['id']}/claim", json={"version": ticket["version"]})
        assert r.status_code == 200, r.text

        assert c.get("/api/v1/notifications/unread-count").json()["count"] == 0

    def test_nguoi_yeu_cau_duoc_bao_khi_ticket_da_xu_ly_xong(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))

        c = login(agent)
        v = c.post(f"/api/v1/tickets/{ticket['id']}/claim", json={"version": ticket["version"]})
        version = v.json()["version"]
        v = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={"status": "IN_PROGRESS", "version": version},
        )
        version = v.json()["version"]
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            json={
                "status": "RESOLVED",
                "version": version,
                "resolutionNote": "Đã thay hộp mực và vệ sinh trục cuốn giấy",
            },
        )
        assert r.status_code == 200, r.text

        c = login(nhan_vien)
        loai = [n["type"] for n in c.get("/api/v1/notifications").json()["data"]]
        assert "TICKET_RESOLVED" in loai


class TestUS33BinhLuan:
    def test_binh_luan_noi_bo_KHONG_bao_cho_nguoi_yeu_cau(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """BR-10 — người yêu cầu không nhìn thấy bình luận nội bộ, nên một
        thông báo "có phản hồi mới" sẽ dẫn tới ticket không có gì mới, đồng
        thời tự tố cáo rằng tồn tại lớp bình luận ẩn."""
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))

        c = login(agent)
        c.post(f"/api/v1/tickets/{ticket['id']}/claim", json={"version": ticket["version"]})
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/comments",
            json={
                "body": "Cần kiểm tra lại hợp đồng bảo hành trước khi trả lời",
                "isInternal": True,
            },
        )
        assert r.status_code == 201, r.text

        c = login(nhan_vien)
        loai = [n["type"] for n in c.get("/api/v1/notifications").json()["data"]]
        assert "TICKET_COMMENTED" not in loai

    def test_binh_luan_cong_khai_CO_bao_cho_nguoi_yeu_cau(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login(nhan_vien))

        c = login(agent)
        c.post(f"/api/v1/tickets/{ticket['id']}/claim", json={"version": ticket["version"]})
        c.post(
            f"/api/v1/tickets/{ticket['id']}/comments",
            json={"body": "Anh chị cho em xin ảnh chụp màn hình báo lỗi nhé", "isInternal": False},
        )

        c = login(nhan_vien)
        loai = [n["type"] for n in c.get("/api/v1/notifications").json()["data"]]
        assert "TICKET_COMMENTED" in loai


class TestUS36XemVaDanhDauDaDoc:
    def test_chi_thay_thong_bao_cua_CHINH_MINH(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)
        nguoi_ngoai = make_user()

        ticket = tao_ticket(login(nhan_vien))
        c = login(admin)
        c.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            json={"assigneeId": str(agent.id), "version": ticket["version"]},
        )

        c = login(nguoi_ngoai)
        assert c.get("/api/v1/notifications").json()["data"] == []
        assert c.get("/api/v1/notifications/unread-count").json()["count"] == 0

    def test_danh_dau_da_doc_lam_giam_so_chua_doc(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)

        ticket = tao_ticket(login(nhan_vien))
        c = login(admin)
        c.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            json={"assigneeId": str(agent.id), "version": ticket["version"]},
        )

        c = login(agent)
        thong_bao = c.get("/api/v1/notifications").json()["data"][0]
        assert c.post(f"/api/v1/notifications/{thong_bao['id']}/read").json()["updated"] == 1
        assert c.get("/api/v1/notifications/unread-count").json()["count"] == 0

        # Đánh dấu lại lần nữa không hỏng, chỉ là không đổi gì
        assert c.post(f"/api/v1/notifications/{thong_bao['id']}/read").json()["updated"] == 0

    def test_danh_dau_thong_bao_cua_NGUOI_KHAC_tra_404_khong_phai_403(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """403 tự xác nhận thông báo đó có tồn tại — cùng nguyên tắc với
        ticket ở BR-09."""
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)
        ke_to_mo = make_user()

        ticket = tao_ticket(login(nhan_vien))
        c = login(admin)
        c.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            json={"assigneeId": str(agent.id), "version": ticket["version"]},
        )

        cua_agent = login(agent).get("/api/v1/notifications").json()["data"][0]["id"]

        c = login(ke_to_mo)
        assert c.post(f"/api/v1/notifications/{cua_agent}/read").status_code == 404

    def test_danh_dau_tat_ca_da_doc(self, client, make_user, login, sla_policies, ticket_category):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)

        c_admin = login(admin)
        for i in range(2):
            ticket = tao_ticket(login(nhan_vien), f"Sự cố số {i} cần hỗ trợ gấp")
            c_admin = login(admin)
            c_admin.post(
                f"/api/v1/tickets/{ticket['id']}/assign",
                json={"assigneeId": str(agent.id), "version": ticket["version"]},
            )

        c = login(agent)
        truoc = c.get("/api/v1/notifications/unread-count").json()["count"]
        assert truoc >= 1

        assert c.post("/api/v1/notifications/read-all").json()["updated"] == truoc
        assert c.get("/api/v1/notifications/unread-count").json()["count"] == 0

    def test_loc_chi_lay_chua_doc(self, client, make_user, login, sla_policies, ticket_category):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
        admin = make_user(role=UserRole.ADMIN)

        ticket = tao_ticket(login(nhan_vien))
        c = login(admin)
        c.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            json={"assigneeId": str(agent.id), "version": ticket["version"]},
        )

        c = login(agent)
        thong_bao = c.get("/api/v1/notifications").json()["data"][0]
        c.post(f"/api/v1/notifications/{thong_bao['id']}/read")

        assert c.get("/api/v1/notifications?unreadOnly=true").json()["data"] == []
        assert len(c.get("/api/v1/notifications").json()["data"]) == 1

    def test_can_dang_nhap_moi_xem_duoc(self, client):
        assert client.get("/api/v1/notifications/unread-count").status_code == 401
