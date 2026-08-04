"""Test API sửa/xoá bình luận — US-15.

Chạy cùng test_tickets.py để chắc không làm hỏng phần đã có:

    .venv-tools/bin/pytest tests/api/test_binh_luan_sua_xoa.py tests/api/test_tickets.py -v
"""

import pytest

from app.modules.users.constants import UserRole

BASE = "/api/v1/tickets"

TICKET_BODY = {
    "title": "Không kết nối được WiFi công ty tại tầng 5",
    "description": "Từ sáng nay máy tôi không thấy mạng CTY-WIFI, đã thử khởi động lại.",
}


def create_ticket(c, **overrides) -> dict:
    body = {**TICKET_BODY, **overrides}
    response = c.post(BASE, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def create_comment(c, ticket_id: str, **overrides) -> dict:
    body = {"body": "Bình luận mẫu để test.", **overrides}
    response = c.post(f"{BASE}/{ticket_id}/comments", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def as_user(client, login, user):
    """Đổi danh tính trên cùng một client."""
    client.headers.pop("Authorization", None)
    login(user)
    return client


@pytest.fixture
def employee_client(client, make_user, login, sla_policies):
    user = make_user(role=UserRole.EMPLOYEE)
    login(user)
    client.current_user = user
    return client


class TestSuaBinhLuan:
    """PATCH /tickets/{id}/comments/{comment_id} — US-15."""

    def test_tac_gia_sua_binh_luan_cua_minh(self, employee_client):
        ticket = create_ticket(employee_client)
        comment = create_comment(employee_client, ticket["id"])

        response = employee_client.patch(
            f"{BASE}/{ticket['id']}/comments/{comment['id']}",
            json={"body": "Đã cập nhật lại nội dung."},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["body"] == "Đã cập nhật lại nội dung."
        assert body["editedAt"] is not None

    def test_nguoi_khac_sua_bi_tu_choi(self, client, make_user, login, sla_policies):
        """Người vẫn XEM được ticket (ở đây là người tạo) nhưng không phải
        tác giả bình luận — trường hợp này phải là 403, khác với người
        không xem được ticket (phải là 404, xem test bên dưới)."""
        requester = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        as_user(client, login, requester)
        ticket = create_ticket(client)

        as_user(client, login, agent)
        client.post(f"{BASE}/{ticket['id']}/claim", json={"version": ticket["version"]})
        comment = create_comment(client, ticket["id"], body="Đang kiểm tra switch tầng 5.")

        # requester nhìn thấy ticket (là người tạo) nhưng không phải tác giả bình luận này
        as_user(client, login, requester)
        response = client.patch(
            f"{BASE}/{ticket['id']}/comments/{comment['id']}",
            json={"body": "Tôi sửa bình luận của agent"},
        )
        assert response.status_code == 403

    def test_sua_binh_luan_tren_ticket_da_dong_bi_tu_choi(
        self, client, make_user, login, sla_policies
    ):
        """Ticket CLOSED thì lịch sử trao đổi phải đứng yên → 422.

        ⚠️ Chuỗi chuyển trạng thái dưới đây (NEW → ASSIGNED → IN_PROGRESS →
        RESOLVED → CLOSED) suy ra từ `test_xu_ly_xong_ghi_lai_moc_thoi_gian`
        trong test_tickets.py. Nếu vai trò được phép gọi bước CLOSED cuối
        cùng không phải `agent` như dưới đây, sửa lại theo đúng
        `state_machine.py` — mình chưa có file đó để xác nhận 100%.
        """
        requester = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        as_user(client, login, requester)
        ticket = create_ticket(client)

        as_user(client, login, agent)
        client.post(f"{BASE}/{ticket['id']}/claim", json={"version": ticket["version"]}).json()
        comment = create_comment(client, ticket["id"])

        current = client.get(f"{BASE}/{ticket['id']}").json()
        started = client.post(
            f"{BASE}/{ticket['id']}/status",
            json={"status": "IN_PROGRESS", "version": current["version"]},
        ).json()
        resolved = client.post(
            f"{BASE}/{ticket['id']}/status",
            json={
                "status": "RESOLVED",
                "resolutionNote": "Đã reset lại cấu hình DHCP trên switch tầng 5.",
                "version": started["version"],
            },
        ).json()
        as_user(client, login, requester)
        closed = client.post(
            f"{BASE}/{ticket['id']}/status",
            json={"status": "CLOSED", "version": resolved["version"]},
        )
        assert closed.status_code == 200, closed.text

        as_user(client, login, agent)
        response = client.patch(
            f"{BASE}/{ticket['id']}/comments/{comment['id']}",
            json={"body": "Cố sửa sau khi đã đóng"},
        )
        assert response.status_code == 422

    def test_comment_id_khong_thuoc_ticket_id_trong_url(self, employee_client):
        ticket_1 = create_ticket(employee_client)
        ticket_2 = create_ticket(employee_client, title="Sự cố khác không liên quan gì")
        comment_o_ticket_2 = create_comment(employee_client, ticket_2["id"])

        response = employee_client.patch(
            f"{BASE}/{ticket_1['id']}/comments/{comment_o_ticket_2['id']}",
            json={"body": "Nhầm ticket"},
        )
        assert response.status_code == 404

    def test_nguoi_khong_duoc_xem_ticket_tra_404_khong_phai_403(
        self, client, make_user, login, sla_policies
    ):
        owner = make_user()
        outsider = make_user()

        as_user(client, login, owner)
        ticket = create_ticket(client)
        comment = create_comment(client, ticket["id"])

        as_user(client, login, outsider)
        response = client.patch(
            f"{BASE}/{ticket['id']}/comments/{comment['id']}",
            json={"body": "Xem trộm rồi sửa"},
        )
        assert response.status_code == 404


class TestXoaBinhLuan:
    """DELETE /tickets/{id}/comments/{comment_id} — US-15."""

    def test_admin_xoa_binh_luan_nguoi_khac(self, client, make_user, login, sla_policies):
        requester = make_user()
        admin = make_user(role=UserRole.ADMIN)

        as_user(client, login, requester)
        ticket = create_ticket(client)
        comment = create_comment(client, ticket["id"])

        as_user(client, login, admin)
        response = client.delete(f"{BASE}/{ticket['id']}/comments/{comment['id']}")
        assert response.status_code == 204

        # bình luận đã xoá mềm thì không còn xuất hiện khi liệt kê
        as_user(client, login, requester)
        comments = client.get(f"{BASE}/{ticket['id']}/comments").json()
        assert comment["id"] not in [c["id"] for c in comments]

    def test_tac_gia_tu_xoa_binh_luan_cua_minh(self, employee_client):
        ticket = create_ticket(employee_client)
        comment = create_comment(employee_client, ticket["id"])

        response = employee_client.delete(f"{BASE}/{ticket['id']}/comments/{comment['id']}")
        assert response.status_code == 204

    def test_nguoi_khac_khong_phai_admin_khong_xoa_duoc(
        self, client, make_user, login, sla_policies
    ):
        requester = make_user()
        agent = make_user(role=UserRole.IT_AGENT)

        as_user(client, login, requester)
        ticket = create_ticket(client)
        comment = create_comment(client, ticket["id"])

        as_user(client, login, agent)
        client.post(f"{BASE}/{ticket['id']}/claim", json={"version": ticket["version"]})

        response = client.delete(f"{BASE}/{ticket['id']}/comments/{comment['id']}")
        assert response.status_code == 403
