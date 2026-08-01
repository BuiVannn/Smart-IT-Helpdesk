"""`is_on_duty()` phải hiểu giờ hành chính là GIỜ ĐỊA PHƯƠNG (P0-2b).

★ VÌ SAO PHẢI CÓ FILE RIÊNG. Lỗi múi giờ ở `is_on_duty()` sống sót qua toàn
bộ bộ test cũ vì `test_assignee_scorer.py` chỉ kiểm `AssigneeScorer` — lớp
thuần nhận sẵn cờ `on_duty=True/False` — chứ không kiểm hàm QUYẾT ĐỊNH cờ đó.
Mọi mốc thời gian trong test lại viết bằng UTC, nên test và code sai cùng một
kiểu và che nhau.

Hậu quả thật: 10 giờ sáng thứ Tư ở Việt Nam là 03:00 UTC, nằm ngoài 8:30–17:30
⇒ **mọi Agent bị coi là ngoài ca trong suốt giờ làm việc thật**, và trọng số
ca trực (0,15) mất tác dụng hoàn toàn.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.modules.tickets.suggestions import AssigneeSuggestionService

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def gio_vn(y, m, d, h, mi=0) -> datetime:
    """Mốc theo giờ Việt Nam, quy về UTC — đúng như dữ liệu vào database."""
    return datetime(y, m, d, h, mi, tzinfo=VN).astimezone(UTC)


@pytest.fixture
def dich_vu(db):
    return AssigneeSuggestionService(db)


class TestGioLamViecTheoGioVietNam:
    @pytest.mark.parametrize(
        ("gio", "trong_ca"),
        [
            (7, False),  # trước giờ mở cửa
            (9, True),  # giữa buổi sáng
            (12, True),  # nghỉ trưa vẫn tính là trong ca (chưa có lịch nghỉ trưa)
            (17, True),  # sát giờ đóng cửa
            (18, False),  # sau giờ đóng cửa
            (22, False),  # buổi tối
            (3, False),  # rạng sáng — chính là 20:00 hôm trước theo UTC
        ],
    )
    def test_theo_gio_trong_ngay(self, dich_vu, gio, trong_ca):
        """★ Mốc 3 giờ sáng là ca then chốt: 03:00 giờ VN = 20:00 UTC hôm
        trước. Bản cũ so thẳng với UTC nên coi đây là "trong ca"."""
        now = gio_vn(2026, 7, 29, gio)  # thứ Tư
        vua_dang_nhap = now - timedelta(hours=1)

        assert dich_vu.is_on_duty(vua_dang_nhap, now) is trong_ca

    def test_10_gio_sang_ngay_lam_viec_LA_trong_ca(self, dich_vu):
        """Triệu chứng gốc của lỗi, viết thành một khẳng định thẳng."""
        now = gio_vn(2026, 7, 29, 10)

        assert dich_vu.is_on_duty(now - timedelta(minutes=30), now) is True

    def test_cuoi_tuan_luon_ngoai_ca(self, dich_vu):
        now = gio_vn(2026, 8, 1, 10)  # thứ Bảy

        assert dich_vu.is_on_duty(now - timedelta(minutes=30), now) is False


class TestDieuKienDangNhapGanDay:
    def test_lau_khong_dang_nhap_thi_ngoai_ca(self, dich_vu):
        """Xấp xỉ hiện tại: "trong ca" = giờ hành chính VÀ có đăng nhập gần
        đây. Đây là chỗ tạm, sẽ thay bằng bảng `agent_shifts` (US-48)."""
        now = gio_vn(2026, 7, 29, 10)

        assert dich_vu.is_on_duty(now - timedelta(days=3), now) is False

    def test_chua_tung_dang_nhap_thi_ngoai_ca(self, dich_vu):
        now = gio_vn(2026, 7, 29, 10)

        assert dich_vu.is_on_duty(None, now) is False
