"""Unit test cho RuleBasedClassifier — đường dự phòng của F3 (US-19, tầng 4).

Lớp này KHÔNG chạm database và KHÔNG gọi LLM, nên test chạy trong mili-giây
và không cần API key. Nó cũng chính là thứ giữ cho F3 demo được khi nhà cung
cấp LLM hỏng hoặc hết hạn mức miễn phí.
"""

import pytest

from app.modules.tickets.classifier import (
    RULE_CONFIDENCE,
    ClassificationSource,
    RuleBasedClassifier,
    normalize,
    sanitize_reasoning,
)
from app.modules.tickets.constants import TicketPriority


@pytest.fixture
def rules() -> RuleBasedClassifier:
    return RuleBasedClassifier()


class TestBoDau:
    """Nhân viên gõ không dấu nhiều không kém gõ có dấu."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Mật khẩu", "mat khau"),
            ("MẠNG WiFi", "mang wifi"),
            ("Đăng nhập", "dang nhap"),
            ("đổi Mật Khẩu", "doi mat khau"),
            ("Email", "email"),
        ],
    )
    def test_bo_dau_va_ha_chu_thuong(self, raw, expected):
        assert normalize(raw) == expected

    def test_go_khong_dau_van_khop(self, rules):
        co_dau = rules.classify("Quên mật khẩu", "Tôi quên mật khẩu đăng nhập máy tính")
        khong_dau = rules.classify("Quen mat khau", "Toi quen mat khau dang nhap may tinh")

        assert co_dau is not None and khong_dau is not None
        assert co_dau.category_slug == khong_dau.category_slug == "account"


class TestPhanLoaiTheoTuKhoa:
    @pytest.mark.parametrize(
        ("title", "description", "expected_slug"),
        [
            ("Không vào được WiFi", "Máy không thấy mạng CTY-WIFI từ sáng", "network"),
            ("Quên mật khẩu", "Tôi cần đặt lại mật khẩu đăng nhập", "account"),
            ("Máy in không chạy", "Máy in tầng 3 không nhận lệnh in", "hardware"),
            ("Cài Office", "Cần cài đặt phần mềm Office cho máy mới", "software"),
            ("Nghi ngờ virus", "Máy hiện cảnh báo virus liên tục", "security"),
            ("Không nhận được email", "Hộp thư Outlook không nhận mail mới", "email"),
            ("Xin quyền thư mục", "Cần cấp quyền truy cập thư mục chung của phòng", "access"),
        ],
    )
    def test_khop_dung_loai(self, rules, title, description, expected_slug):
        suggestion = rules.classify(title, description)

        assert suggestion is not None
        assert suggestion.category_slug == expected_slug
        assert suggestion.source == ClassificationSource.RULES

    def test_khong_khop_thi_tra_none(self, rules):
        """Thà không đoán còn hơn đoán bừa — ticket sẽ vào hàng chờ thủ công."""
        assert rules.classify("Xin chào", "Tôi muốn hỏi về quy trình nghỉ phép") is None

    def test_luon_duoi_nguong_ap_dung(self, rules):
        """★ Bất biến quan trọng nhất của lớp này.

        Đối chiếu từ khoá đủ tốt để GỢI Ý cho Agent, không đủ tốt để tự động
        đổi dữ liệu của người dùng. Nếu ai đó nâng RULE_CONFIDENCE lên trên
        ngưỡng, hệ thống sẽ âm thầm tự áp dụng kết quả đoán bằng từ khoá.
        """
        suggestion = rules.classify("Mất mạng", "Cả tầng 5 không vào được internet")

        assert suggestion is not None
        assert suggestion.confidence == RULE_CONFIDENCE
        assert RULE_CONFIDENCE < 0.6

    def test_bao_mat_thang_phan_cung(self, rules):
        """"Máy tính dính virus" phải vào `security`, không phải `hardware`.

        Cả hai luật đều khớp; luật bảo mật đứng trước nên thắng khi hoà.
        """
        suggestion = rules.classify("Máy tính dính virus", "Laptop của tôi bị nhiễm virus")

        assert suggestion is not None
        assert suggestion.category_slug == "security"
        assert suggestion.priority == TicketPriority.URGENT

    def test_nhieu_tu_khoa_thang_it_tu_khoa(self, rules):
        """Luật khớp nhiều từ khoá hơn thì thắng, kể cả khi đứng sau trong bảng."""
        suggestion = rules.classify(
            "Xin cấp quyền truy cập",
            "Cần cấp quyền vào thư mục chung, hiện chưa có quyền truy cập",
        )

        assert suggestion is not None
        assert suggestion.category_slug == "access"

    def test_ranh_gioi_tu_khong_khop_bua(self, rules):
        """"mang" không được khớp bên trong một từ khác.

        Không có ranh giới từ, mọi mô tả chứa "mangan", "khoảng" (sau khi bỏ
        dấu) đều bị gán vào `network`.
        """
        suggestion = rules.classify(
            "Đặt mua hoá chất", "Cần mua mangan cho phòng thí nghiệm"
        )
        assert suggestion is None or suggestion.category_slug != "network"

    def test_ly_do_neu_ro_tu_khoa_da_khop(self, rules):
        suggestion = rules.classify("Mất mạng", "Không vào được internet")

        assert suggestion is not None
        assert "từ khoá" in suggestion.reasoning.lower()


class TestLamSachReasoning:
    def test_cat_con_300_ky_tu(self):
        assert len(sanitize_reasoning("a" * 500)) == 300

    def test_gop_khoang_trang_va_bo_ky_tu_dieu_khien(self):
        assert sanitize_reasoning("Lý do\x00  có\nnhiều   khoảng") == "Lý do có nhiều khoảng"

    def test_chuoi_rong(self):
        assert sanitize_reasoning("") == ""


class TestFakeLlmKhongDinhVaoDanhSachCategory:
    """★ Prompt phân loại LUÔN kèm danh sách loại sự cố, trong đó có dòng
    "- network: Mạng & Internet". Nếu FakeLlmClient khớp từ khoá trên toàn bộ
    prompt, nó dính "mạng"/"internet" ở danh sách đó và trả `network` cho MỌI
    ticket — kể cả ticket nói về virus.

    Mặc định `LLM_PROVIDER=fake`, nên đây đúng là thứ người xem demo nhìn thấy.
    """

    @staticmethod
    def _prompt(title: str, description: str) -> str:
        from app.modules.tickets.prompts import build_classify_prompt

        _, user = build_classify_prompt(
            title=title,
            description=description,
            categories=[
                ("network", "Mạng & Internet"),
                ("security", "Bảo mật"),
                ("hardware", "Phần cứng & Thiết bị"),
            ],
        )
        return user

    @pytest.mark.parametrize(
        ("title", "description", "expected"),
        [
            ("Nghi ngờ nhiễm virus", "Máy hiện cảnh báo virus liên tục", "security"),
            ("Máy in hỏng", "Máy in tầng 3 không nhận lệnh", "hardware"),
            ("Mất WiFi", "Không vào được mạng CTY-WIFI", "network"),
        ],
    )
    def test_phan_loai_theo_noi_dung_ticket(self, title, description, expected):
        from app.ai.llm.fake_client import FakeLlmClient

        result = FakeLlmClient()._classify(self._prompt(title, description))

        assert result["category_slug"] == expected

    def test_bao_mat_thang_phan_mem_trong_fake_llm(self):
        """"Phần mềm diệt virus báo phát hiện mã độc" khớp cả hai luật.

        Luật khớp đầu tiên thắng, nên bảo mật phải đứng đầu bảng — nếu không,
        một sự cố mã độc bị xếp vào `software` và đi sai hàng chờ.
        """
        from app.ai.llm.fake_client import FakeLlmClient

        result = FakeLlmClient()._classify(
            self._prompt(
                "Máy tính liên tục cảnh báo nhiễm virus",
                "Phần mềm diệt virus báo phát hiện mã độc, máy chạy rất chậm.",
            )
        )

        assert result["category_slug"] == "security"
        assert result["priority"] == "URGENT"
