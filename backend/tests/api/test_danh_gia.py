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


class TestXemDanhGiaCuaAgent:
    """`GET /tickets/ratings/mine` — Agent xem đánh giá về mình (US-43)."""
 
    def test_agent_xem_duoc_danh_gia_cua_minh(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
 
        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])
 
        c = login(nhan_vien)
        r = c.post(
            f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 4, "comment": "Ổn"}
        )
        assert r.status_code == 201, r.text
 
        c = login(agent)
        r = c.get("/api/v1/tickets/ratings/mine")
 
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pagination"]["totalItems"] == 1
        item = body["data"][0]
        assert item["score"] == 4
        assert item["comment"] == "Ổn"
        assert item["ticketId"] == ticket["id"]
        assert item["ticketCode"] == ticket["code"]
 
    def test_an_danh_nguoi_cham_diem(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        """★ AC của US-42/US-43: Agent chỉ thấy điểm và nhận xét, không thấy
        ai chấm. Không có `raterId`/`raterName` (hay bất kỳ field nào định
        danh người đánh giá) trong response — kể cả dưới tên khác."""
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
 
        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])
 
        c = login(nhan_vien)
        r = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 5})
        assert r.status_code == 201, r.text
 
        c = login(agent)
        r = c.get("/api/v1/tickets/ratings/mine")
 
        item = r.json()["data"][0]
        loi_bi_cam = {"raterId", "raterName", "rater_id", "rater", "nguoiDanhGia", "requesterId"}
        assert loi_bi_cam.isdisjoint(item.keys())
 
    def test_agent_khong_thay_danh_gia_cua_agent_khac(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent_a = make_user(role=UserRole.IT_AGENT)
        agent_b = make_user(role=UserRole.IT_AGENT)
 
        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent_a, ticket["id"], ticket["version"])
 
        c = login(nhan_vien)
        r = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 3})
        assert r.status_code == 201, r.text
 
        c = login(agent_b)
        r = c.get("/api/v1/tickets/ratings/mine")
 
        assert r.status_code == 200, r.text
        assert r.json()["pagination"]["totalItems"] == 0
 
    def test_ticket_chua_duoc_danh_gia_khong_xuat_hien(
        self, client, make_user, login, sla_policies, ticket_category
    ):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
 
        ticket = tao_ticket(login, nhan_vien)
        dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])
        # Không gửi đánh giá nào.
 
        c = login(agent)
        r = c.get("/api/v1/tickets/ratings/mine")
 
        assert r.status_code == 200, r.text
        assert r.json()["pagination"]["totalItems"] == 0
 
    def test_nhan_vien_bi_tu_choi(self, client, make_user, login):
        """`require_agent` chỉ cho IT_AGENT và ADMIN — Employee không có
        \"đánh giá về mình\" vì Employee không xử lý ticket."""
        nhan_vien = make_user()
        c = login(nhan_vien)
 
        r = c.get("/api/v1/tickets/ratings/mine")
 
        assert r.status_code == 403
 
    def test_phan_trang(self, client, make_user, login, sla_policies, ticket_category):
        nhan_vien = make_user()
        agent = make_user(role=UserRole.IT_AGENT)
 
        for _ in range(3):
            ticket = tao_ticket(login, nhan_vien)
            dua_toi_closed(login, nhan_vien, agent, ticket["id"], ticket["version"])
            c = login(nhan_vien)
            r = c.post(f"/api/v1/tickets/{ticket['id']}/rating", json={"score": 5})
            assert r.status_code == 201, r.text
 
        c = login(agent)
        r = c.get("/api/v1/tickets/ratings/mine", params={"pageSize": 2, "page": 1})
 
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["totalItems"] == 3
        assert body["pagination"]["totalPages"] == 2      
        