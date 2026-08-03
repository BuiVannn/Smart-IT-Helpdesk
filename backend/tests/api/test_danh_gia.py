"""API đánh giá sau xử lý — US-41.

★ Fixture `login` ở conftest hiện dùng CHUNG một `TestClient` (ghi đè
header `Authorization` ngay trên chính client đó, không tạo client mới).
Nghĩa là hai biến lấy từ hai lần gọi `login()` khác nhau LÀ CÙNG MỘT OBJECT
— gọi `login(b)` sau `login(a)` sẽ đổi danh tính của CẢ HAI biến.

Do đó tuyệt đối không giữ một client đã login rồi dùng lại ở bước sau khi
đã login người khác xen giữa. Luôn `login(user)` NGAY TRƯỚC khi gửi request
cần đúng danh tính đó — xem các hàm `tao_ticket`, `dua_toi_*` dưới đây.
"""

from app.modules.users.constants import UserRole

MO_TA = "Mô tả đủ dài để qua ràng buộc CHECK của bảng tickets."


def tao_ticket(login, nhan_vien, tieu_de="Sự cố cần đánh giá"):
    c = login(nhan_vien)
    r = c.post("/api/v1/tickets", json={"title": tieu_de, "description": MO_TA})
    assert r.status_code == 201, r.text
    return r.json()


def dua_toi_in_progress(login, agent, ticket_id, version):
    c = login(agent)
    r = c.post(f"/api/v1/tickets/{ticket_id}/claim", json={"version": version})
    assert r.status_code == 200, r.text
    version = r.json()["version"]

    c = login(agent)  # re-login cho chắc, không giả định header còn nguyên
    r = c.post(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS", "version": version},
    )
    assert r.status_code == 200, r.text
    return r.json()["version"]


def dua_toi_resolved(login, agent, ticket_id, version):
    version = dua_toi_in_progress(login, agent, ticket_id, version)
    c = login(agent)
    r = c.post(
        f"/api/v1/tickets/{ticket_id}/status",
        json={
            "status": "RESOLVED",
            "version": version,
            "resolutionNote": "Đã thay thiết bị và kiểm tra lại",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["version"]


def dua_toi_closed(login, nhan_vien, agent, ticket_id, version):
    version = dua_toi_resolved(login, agent, ticket_id, version)
    c = login(nhan_vien)  # ★ đổi LẠI đúng người tạo ngay trước khi đóng
    r = c.post(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "CLOSED", "version": version},
    )
    assert r.status_code == 200, r.text
    return r.json()["version"]


class TestTaoDanhGia:
    def test_danh_gia_ticket_closed_thanh_cong(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])

        c = login(nhan_vien)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 5, "comment": "Tốt"}
        )

        assert r.status_code == 201, r.text
        body = r.json()
        assert body["score"] == 5
        assert body["ticketId"] == ticket["id"]
        assert body["isEditable"] is True

    def test_danh_gia_ticket_dang_xu_ly_bi_tu_choi(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """Ticket còn IN_PROGRESS — chưa xử lý xong thì chưa có gì để đánh giá."""
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login, nhan_vien)
        dua_toi_in_progress(login, agent, ticket["id"], ticket["version"])

        c = login(nhan_vien)
        r = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 4})

        assert r.status_code == 422

    def test_danh_gia_ticket_khong_phai_cua_minh_tra_404(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """BR-09: 404 chứ không phải 403, để không tiết lộ ticket đó có tồn tại."""
        nhan_vien = make_user()
        nguoi_khac = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])

        c = login(nguoi_khac)
        r = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 3})

        assert r.status_code == 404

    def test_danh_gia_lan_hai_tra_409(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])

        c = login(nhan_vien)
        r1 = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 5})
        assert r1.status_code == 201, r1.text

        c = login(nhan_vien)
        r2 = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 2})
        assert r2.status_code == 409

    def test_score_ngoai_khoang_tra_422(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])

        c = login(nhan_vien)
        r0 = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 0})
        assert r0.status_code == 422

        c = login(nhan_vien)
        r6 = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 6})
        assert r6.status_code == 422


class TestSuaDanhGia:
    def test_sua_trong_24_gio_thanh_cong(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])

        c = login(nhan_vien)
        r1 = c.post(
            f"/api/v1/tickets/{ticket['id']}/rating",
            json={"score": 3, "comment": "Tạm được"},
        )
        assert r1.status_code == 201, r1.text

        c = login(nhan_vien)
        r2 = c.patch(
            f"/api/v1/tickets/{ticket['id']}/rating",
            json={"score": 5, "comment": "Sau khi kiểm tra lại thì rất tốt"},
        )

        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["score"] == 5
        assert body["comment"] == "Sau khi kiểm tra lại thì rất tốt"
        
        