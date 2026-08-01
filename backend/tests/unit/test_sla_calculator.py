"""★ TEST MẪU cho lớp thuần — copy cấu trúc này khi viết test cho lớp khác.

Đặc điểm: KHÔNG dùng database, KHÔNG dùng network, chạy trong mili-giây.
"""

from datetime import UTC, date, datetime

import pytest

from app.modules.tickets.constants import SlaState
from app.modules.tickets.sla import BusinessCalendar, SlaCalculator


def dt(y, m, d, h=0, mi=0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=UTC)


@pytest.fixture
def calculator() -> SlaCalculator:
    # 2026-09-02 là ngày lễ Quốc khánh
    return SlaCalculator(BusinessCalendar(holidays=frozenset({date(2026, 9, 2)})))


class TestDueAt:
    def test_trong_gio_lam_viec_thi_cong_thang(self, calculator):
        # Thứ Tư 09:00 + 2 giờ = 11:00 cùng ngày
        assert calculator.due_at(dt(2026, 7, 29, 9, 0), 120) == dt(2026, 7, 29, 11, 0)

    def test_vat_qua_dem(self, calculator):
        # Thứ Tư 17:00 + 2 giờ ⇒ còn 30 phút hôm nay, 90 phút sang thứ Năm
        assert calculator.due_at(dt(2026, 7, 29, 17, 0), 120) == dt(2026, 7, 30, 10, 0)

    def test_chieu_thu_sau_nhay_qua_thu_hai(self, calculator):
        """★ CA QUAN TRỌNG NHẤT — ticket URGENT (SLA 4 giờ làm việc) tạo lúc
        17:00 thứ Sáu phải có hạn 11:30 sáng THỨ HAI, không phải 21:00 thứ Sáu.

        Nếu ca này sai, toàn bộ tính năng cảnh báo SLA sai và không ai phát
        hiện cho đến lúc demo.
        """
        # Thứ Sáu 2026-07-31 17:00, SLA 240 phút
        # → 30 phút còn lại hôm nay, 210 phút còn lại vào thứ Hai từ 8:30 → 12:00
        result = calculator.due_at(dt(2026, 7, 31, 17, 0), 240)
        assert result.date() == date(2026, 8, 3)  # thứ Hai
        assert result == dt(2026, 8, 3, 12, 0)

    def test_bo_qua_ngay_le(self, calculator):
        # Thứ Ba 2026-09-01 17:00 + 2 giờ, mà 02/09 là lễ ⇒ nhảy sang 03/09
        result = calculator.due_at(dt(2026, 9, 1, 17, 0), 120)
        assert result.date() == date(2026, 9, 3)

    def test_tao_ngoai_gio_thi_tinh_tu_dau_gio_hom_sau(self, calculator):
        # Thứ Tư 22:00 ⇒ bắt đầu tính từ thứ Năm 8:30
        assert calculator.due_at(dt(2026, 7, 29, 22, 0), 60) == dt(2026, 7, 30, 9, 30)

    def test_che_do_24_7_thi_cong_thang(self, calculator):
        result = calculator.due_at(dt(2026, 7, 31, 17, 0), 240, business_hours_only=False)
        assert result == dt(2026, 7, 31, 21, 0)


class TestState:
    def test_con_nhieu_thoi_gian(self, calculator):
        state = calculator.state(
            created_at=dt(2026, 7, 30, 9, 0),
            due_at=dt(2026, 7, 30, 17, 0),
            resolved_at=None,
            now=dt(2026, 7, 30, 10, 0),
        )
        assert state == SlaState.ON_TRACK

    def test_sap_het_han(self, calculator):
        state = calculator.state(
            created_at=dt(2026, 7, 30, 9, 0),
            due_at=dt(2026, 7, 30, 17, 0),
            resolved_at=None,
            now=dt(2026, 7, 30, 16, 0),
        )
        assert state == SlaState.AT_RISK

    def test_da_qua_han(self, calculator):
        state = calculator.state(
            created_at=dt(2026, 7, 30, 9, 0),
            due_at=dt(2026, 7, 30, 17, 0),
            resolved_at=None,
            now=dt(2026, 7, 30, 18, 0),
        )
        assert state == SlaState.BREACHED

    def test_xu_ly_xong_truoc_han(self, calculator):
        state = calculator.state(
            created_at=dt(2026, 7, 30, 9, 0),
            due_at=dt(2026, 7, 30, 17, 0),
            resolved_at=dt(2026, 7, 30, 15, 0),
            now=dt(2026, 7, 30, 18, 0),
        )
        assert state == SlaState.MET

    def test_thoi_gian_cho_nguoi_dung_khong_tinh_vao_sla(self, calculator):
        """Thời gian ở PENDING_REQUESTER không phải lỗi của Agent."""
        state = calculator.state(
            created_at=dt(2026, 7, 30, 9, 0),
            due_at=dt(2026, 7, 30, 17, 0),
            resolved_at=None,
            now=dt(2026, 7, 30, 18, 0),
            paused_seconds=7200,  # đã chờ người dùng 2 giờ
        )
        assert state != SlaState.BREACHED
