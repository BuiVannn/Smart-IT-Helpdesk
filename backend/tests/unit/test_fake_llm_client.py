"""FakeLlmClient — bộ não mà người xem thấy khi demo chưa cắm API key (P0-4).

`LLM_PROVIDER=fake` là MẶC ĐỊNH (`config.py`), nên mọi khiếm khuyết ở đây là
khiếm khuyết người chấm nhìn thấy trực tiếp, không phải chi tiết nội bộ.
"""

import asyncio
import json

import pytest

from app.ai.llm.fake_client import DEFAULT_CLASSIFICATION, FakeLlmClient
from app.core.config import settings

SCHEMA = {"type": "object"}


@pytest.fixture
def phan_loai():
    client = FakeLlmClient()

    def _phan_loai(mo_ta: str) -> dict:
        prompt = f"Danh sách loại sự cố:\n- network: Mạng & Internet\n\nTiêu đề: {mo_ta}"
        res = asyncio.run(client.complete(system="", user=prompt, schema=SCHEMA))
        return json.loads(res.content)

    return _phan_loai


class TestNhanhKhongBiet:
    def test_do_tin_cay_mac_dinh_PHAI_duoi_nguong_ap_dung(self):
        """★ ĐÂY LÀ LỖI ĐÃ XẢY RA. Nhánh "không luật nào khớp" từng trả
        `confidence = 0,75` — vượt ngưỡng 0,6 — nên hệ thống coi "tôi không
        biết" là một phán đoán tự tin và **ghi thẳng nhãn `other` sai vào
        ticket** thay vì đưa vào hàng chờ phân loại thủ công.

        Đo trên tập 50 ca: chế độ fake đạt 54% category, TỆ HƠN đường dự phòng
        đối chiếu từ khoá (74%).
        """
        assert DEFAULT_CLASSIFICATION["confidence"] < settings.AI_CONFIDENCE_THRESHOLD

    def test_ticket_khong_ro_rang_roi_vao_hang_cho_thu_cong(self, phan_loai):
        ket_qua = phan_loai("Có chuyện này lạ lắm anh xem giúp em với")

        assert ket_qua["category_slug"] == "other"
        assert ket_qua["confidence"] < settings.AI_CONFIDENCE_THRESHOLD


class TestPhuHetLoaiSuCo:
    """Bảng luật phải phủ đủ 8 loại đã seed, không thiếu loại nào."""

    @pytest.mark.parametrize(
        ("mo_ta", "mong_doi"),
        [
            ("Laptop nhiễm virus, có cửa sổ lạ bật lên liên tục", "security"),
            ("Không kết nối được wifi công ty", "network"),
            ("Quên mật khẩu đăng nhập hệ thống", "account"),
            ("Máy in tầng 3 bị kẹt giấy", "hardware"),
            ("Cần cài đặt phần mềm Office cho máy mới", "software"),
            ("Outlook không nhận được mail mới từ sáng nay", "email"),
            ("Xin cấp quyền truy cập thư mục chung của phòng", "access"),
        ],
    )
    def test_khop_dung_loai(self, phan_loai, mo_ta, mong_doi):
        assert phan_loai(mo_ta)["category_slug"] == mong_doi

    def test_email_va_access_khong_con_thieu(self, phan_loai):
        """Hai loại này từng KHÔNG có luật nào, nên mọi ticket email và cấp
        quyền đều rơi vào nhánh mặc định `other`."""
        assert phan_loai("Hòm thư đầy không gửi mail được")["category_slug"] == "email"
        assert phan_loai("Tôi bị thu hồi quyền truy cập báo cáo")["category_slug"] == "access"


class TestThuTuLuat:
    def test_bao_mat_thang_khi_trung_tu_khoa(self, phan_loai):
        """ "Phần mềm diệt virus báo phát hiện mã độc" khớp cả "phần mềm" lẫn
        "virus". Chậm một giờ với mã độc đắt hơn nhiều so với gán nhầm một
        ticket phần mềm."""
        ket_qua = phan_loai("Phần mềm diệt virus báo phát hiện mã độc trên máy")

        assert ket_qua["category_slug"] == "security"
        assert ket_qua["priority"] == "URGENT"

    def test_cap_quyen_thang_tai_khoan(self, phan_loai):
        """ "Xin cấp quyền truy cập" chứa cả "tài khoản" lẫn "quyền truy cập";
        yêu cầu cấp quyền là việc cụ thể hơn nên phải thắng."""
        assert (
            phan_loai("Xin cấp quyền truy cập cho tài khoản của tôi")["category_slug"] == "access"
        )


class TestKhongDocNhamPhanPrompt:
    def test_bo_qua_danh_sach_loai_su_co_o_dau_prompt(self):
        """Prompt phân loại luôn kèm danh sách category, trong đó có dòng
        "- network: Mạng & Internet". Không cắt bỏ phần đó thì MỌI ticket đều
        bị phân loại là `network` — và đây là mặc định khi demo."""
        client = FakeLlmClient()
        prompt = (
            "Danh sách loại sự cố:\n"
            "- network: Mạng & Internet\n"
            "- hardware: Phần cứng & Thiết bị\n\n"
            "Tiêu đề: Máy in tầng 3 bị kẹt giấy"
        )
        res = asyncio.run(client.complete(system="", user=prompt, schema=SCHEMA))

        assert json.loads(res.content)["category_slug"] == "hardware"
