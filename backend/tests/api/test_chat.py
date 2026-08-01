"""Test API chatbot — US-23, US-24.

Trọng tâm là RANH GIỚI HTTP, không phải logic RAG (logic đã có
tests/integration/test_chat_service.py phủ). Cụ thể: quyền truy cập phiên,
định dạng khung SSE, và thứ tự sự kiện.
"""

import json

import pytest

from app.modules.users.constants import UserRole

BASE = "/api/v1/chat"


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    """Tách luồng SSE thành [(tên sự kiện, dữ liệu)].

    Viết tay thay vì dùng thư viện để test bắt được cả lỗi ĐỊNH DẠNG: thiếu
    dòng trống ngăn cách, hay xuống dòng chưa escape trong `data:` — đều làm
    trình duyệt hiểu sai toàn bộ phần còn lại của luồng.
    """
    events: list[tuple[str, dict]] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        name, payload = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                payload = json.loads(line[6:])
        assert name is not None, f"khung SSE thiếu dòng `event:`: {block!r}"
        assert payload is not None, f"khung SSE thiếu dòng `data:`: {block!r}"
        events.append((name, payload))
    return events


@pytest.fixture
def session_id(auth_client) -> str:
    response = auth_client.post(f"{BASE}/sessions", json={"title": "Thử nghiệm"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def ask(client, session_id: str, question: str) -> list[tuple[str, dict]]:
    response = client.post(f"{BASE}/sessions/{session_id}/messages", json={"question": question})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


class TestQuanLyPhien:
    def test_tao_phien(self, auth_client):
        response = auth_client.post(f"{BASE}/sessions", json={"title": "Hỏi về WiFi"})
        assert response.status_code == 201
        body = response.json()
        assert body["messageCount"] == 0
        assert body["ledToTicket"] is False

    def test_chua_dang_nhap_thi_401(self, client):
        assert client.post(f"{BASE}/sessions", json={}).status_code == 401

    def test_chi_thay_phien_cua_minh(self, client, make_user, login):
        a, b = make_user(), make_user()

        client.headers.pop("Authorization", None)
        login(a)
        client.post(f"{BASE}/sessions", json={"title": "Của A"})

        client.headers.pop("Authorization", None)
        login(b)
        body = client.get(f"{BASE}/sessions").json()
        assert body["pagination"]["totalItems"] == 0

    def test_ADMIN_cung_khong_doc_duoc_phien_nguoi_khac(self, client, make_user, login):
        """★ Khác với ticket: hội thoại với trợ lý là việc riêng của nhân viên.

        Nhân viên hỏi "máy tôi nhiễm virus" hay "tôi quên mật khẩu" thì đó
        không phải việc chung của công ty để Admin đọc.
        """
        employee = make_user()
        client.headers.pop("Authorization", None)
        login(employee)
        sid = client.post(f"{BASE}/sessions", json={}).json()["id"]

        client.headers.pop("Authorization", None)
        login(make_user(role=UserRole.ADMIN))
        assert client.get(f"{BASE}/sessions/{sid}").status_code == 404

    def test_hoi_vao_phien_nguoi_khac_tra_404(self, client, make_user, login):
        client.headers.pop("Authorization", None)
        login(make_user())
        sid = client.post(f"{BASE}/sessions", json={}).json()["id"]

        client.headers.pop("Authorization", None)
        login(make_user())
        response = client.post(f"{BASE}/sessions/{sid}/messages", json={"question": "wifi"})
        assert response.status_code == 404


class TestLuongSSE:
    def test_dinh_dang_khung_SSE_hop_le(self, auth_client, session_id, seeded_kb):
        """Mỗi khung phải có `event:`, `data:` và kết bằng một dòng trống."""
        events = ask(auth_client, session_id, "Làm sao đổi mật khẩu email?")
        assert events, "luồng rỗng"
        for name, _ in events:
            assert name in {"citations", "token", "done", "error"}

    def test_thu_tu_su_kien(self, auth_client, session_id, seeded_kb):
        """Hợp đồng với frontend: citations → token* → done."""
        names = [n for n, _ in ask(auth_client, session_id, "wifi công ty")]
        assert names[0] == "citations", "trích dẫn phải tới TRƯỚC nội dung"
        assert names[-1] == "done"
        assert "token" in names

    def test_token_chua_xuong_dong_khong_lam_vo_khung(self, auth_client, session_id, seeded_kb):
        """★ Nếu quên escape "\\n" trong `data:`, một token xuống dòng sẽ cắt
        đôi khung và trình duyệt hiểu sai toàn bộ phần còn lại của luồng."""
        events = ask(auth_client, session_id, "hướng dẫn cài đặt máy in")
        # parse_sse ở trên sẽ ném lỗi nếu có khung hỏng; tới được đây là đạt
        assert [n for n, _ in events][-1] in {"done", "error"}

    def test_luu_lai_lich_su_hoi_thoai(self, auth_client, session_id, seeded_kb):
        ask(auth_client, session_id, "Làm sao đổi mật khẩu email?")

        detail = auth_client.get(f"{BASE}/sessions/{session_id}").json()
        roles = [m["role"] for m in detail["messages"]]
        assert roles == ["USER", "ASSISTANT"]
        assert detail["messageCount"] == 2

    def test_PHAI_commit_khong_chi_flush(self, auth_client, session_id, seeded_kb, db):
        """★ Lỗi này đã xảy ra thật và test cũ KHÔNG bắt được.

        `ChatService` chỉ gọi `flush()` — dữ liệu nằm trong transaction chứ
        chưa xuống đĩa. Luồng SSE ở production mở session RIÊNG và đóng nó khi
        stream kết thúc ⇒ toàn bộ hội thoại bị rollback. Người dùng thấy câu
        trả lời chạy ra, tải lại trang thì trống trơn, không lỗi nào được ghi.

        Các test khác không phát hiện được vì `client` và `db` dùng CHUNG một
        session, nên `flush()` đủ để đọc thấy. Đây là lý do phải kiểm tra
        chính hành vi commit, chứ không kiểm tra "đọc lại có thấy không".
        """
        commits = []
        original = db.commit
        db.commit = lambda: (commits.append(1), original())[1]
        try:
            ask(auth_client, session_id, "Làm sao đổi mật khẩu email?")
        finally:
            db.commit = original

        assert commits, "ChatService không commit lần nào — hội thoại sẽ mất khi session đóng"

    def test_cap_nhat_moc_nhan_tin_cuoi(self, auth_client, session_id, seeded_kb):
        """Thiếu `last_message_at` thì danh sách phiên sắp xếp theo ngày TẠO,
        phiên vừa nhắn nằm dưới phiên mở từ tuần trước."""
        ask(auth_client, session_id, "wifi công ty")
        detail = auth_client.get(f"{BASE}/sessions/{session_id}").json()
        assert detail["lastMessageAt"] is not None

    def test_cau_hoi_rong_bi_tu_choi_o_tang_schema(self, auth_client, session_id):
        response = auth_client.post(f"{BASE}/sessions/{session_id}/messages", json={"question": ""})
        assert response.status_code == 422

    def test_cau_hoi_qua_dai_bi_tu_choi(self, auth_client, session_id):
        response = auth_client.post(
            f"{BASE}/sessions/{session_id}/messages", json={"question": "x" * 1001}
        )
        assert response.status_code == 422


class TestCauHinh:
    def test_tra_ve_gioi_han_cho_frontend(self, auth_client):
        """Frontend hiển thị giới hạn theo số backend trả về, không chép cứng."""
        body = auth_client.get(f"{BASE}/config").json()
        assert body["maxQuestionLength"] == 1000
        assert body["rateLimitPerWindow"] > 0
