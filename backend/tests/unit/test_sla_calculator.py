"""★ TEST MẪU cho lớp thuần — copy cấu trúc này khi viết test cho lớp khác.

Đặc điểm: KHÔNG dùng database, KHÔNG dùng network, chạy trong mili-giây.

★★ MỌI MỐC THỜI GIAN TRONG FILE NÀY VIẾT THEO GIỜ VIỆT NAM.

Bản trước dựng mốc bằng `datetime(..., tzinfo=UTC)` nhưng ĐỌC chúng như giờ
làm việc ("thứ Sáu 17:00"). Hai chuyện đó chỉ trùng nhau nếu văn phòng đặt ở
múi giờ UTC. Vì `SlaCalculator` khi ấy cũng so giờ hành chính với UTC nên
test xanh — test và code sai cùng một kiểu nên che nhau. Dùng `gio_vn()` để
sai lệch đó không lặp lại: đầu vào là giờ người dùng thật sự trải nghiệm.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.tickets.constants import SlaState
from app.modules.tickets.sla import BusinessCalendar, SlaCalculator

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def gio_vn(y, m, d, h=0, mi=0) -> datetime:
    """Một mốc theo giờ Việt Nam, quy về UTC — đúng như dữ liệu vào database."""
    return datetime(y, m, d, h, mi, tzinfo=VN).astimezone(UTC)


def xem_theo_gio_vn(moment: datetime) -> datetime:
    return moment.astimezone(VN)


def dt(y, m, d, h=0, mi=0) -> datetime:
    """Mốc UTC thuần — chỉ dùng cho các test không liên quan giờ hành chính."""
    return datetime(y, m, d, h, mi, tzinfo=UTC)


@pytest.fixture
def calculator() -> SlaCalculator:
    # 2026-09-02 là ngày lễ Quốc khánh
    return SlaCalculator(BusinessCalendar(holidays=frozenset({date(2026, 9, 2)})))


class TestDueAt:
    def test_trong_gio_lam_viec_thi_cong_thang(self, calculator):
        # Thứ Tư 09:00 giờ VN + 2 giờ = 11:00 cùng ngày
        ket_qua = calculator.due_at(gio_vn(2026, 7, 29, 9, 0), 120)
        assert xem_theo_gio_vn(ket_qua) == datetime(2026, 7, 29, 11, 0, tzinfo=VN)

    def test_vat_qua_dem(self, calculator):
        # Thứ Tư 17:00 giờ VN + 2 giờ ⇒ còn 30 phút hôm nay, 90 phút sang thứ Năm
        ket_qua = calculator.due_at(gio_vn(2026, 7, 29, 17, 0), 120)
        assert xem_theo_gio_vn(ket_qua) == datetime(2026, 7, 30, 10, 0, tzinfo=VN)

    def test_chieu_thu_sau_nhay_qua_thu_hai(self, calculator):
        """★ CA QUAN TRỌNG NHẤT — ticket URGENT (SLA 4 giờ làm việc) tạo lúc
        17:00 thứ Sáu **giờ Việt Nam** phải có hạn vào sáng THỨ HAI, không
        phải 21:00 thứ Sáu và cũng không phải tối Chủ nhật.

        Con số đúng là **12:00**, không phải 11:30 như `docs/design/03` §6
        đang ghi: 17:00 → 17:30 còn 30 phút của thứ Sáu, 210 phút còn lại
        tính từ 8:30 thứ Hai ⇒ 12:00. Tài liệu ghi sai 30 phút, đã sửa kèm
        theo lần này.
        """
        ket_qua = calculator.due_at(gio_vn(2026, 7, 31, 17, 0), 240)
        theo_vn = xem_theo_gio_vn(ket_qua)

        assert theo_vn.date() == date(2026, 8, 3)  # thứ Hai
        assert theo_vn == datetime(2026, 8, 3, 12, 0, tzinfo=VN)

    def test_bo_qua_ngay_le(self, calculator):
        # Thứ Ba 2026-09-01 17:00 giờ VN + 2 giờ, mà 02/09 là lễ ⇒ nhảy sang 03/09
        ket_qua = calculator.due_at(gio_vn(2026, 9, 1, 17, 0), 120)
        assert xem_theo_gio_vn(ket_qua).date() == date(2026, 9, 3)

    def test_tao_ngoai_gio_thi_tinh_tu_dau_gio_hom_sau(self, calculator):
        # Thứ Tư 22:00 giờ VN ⇒ bắt đầu tính từ thứ Năm 8:30
        ket_qua = calculator.due_at(gio_vn(2026, 7, 29, 22, 0), 60)
        assert xem_theo_gio_vn(ket_qua) == datetime(2026, 7, 30, 9, 30, tzinfo=VN)

    def test_che_do_24_7_thi_cong_thang(self, calculator):
        result = calculator.due_at(dt(2026, 7, 31, 17, 0), 240, business_hours_only=False)
        assert result == dt(2026, 7, 31, 21, 0)


class TestMuiGio:
    """★ Nhóm test tồn tại riêng để lỗi múi giờ không quay lại lần nữa."""

    def test_ticket_tao_9_gio_sang_KHONG_bao_gio_co_han_sau_gio_lam_viec(self, calculator):
        """Đây chính là triệu chứng của lỗi cũ: ticket tạo 9 giờ sáng thứ Hai
        nhận hạn 4 giờ làm việc là 19:30 cùng ngày — 2 tiếng sau giờ đóng cửa."""
        han = xem_theo_gio_vn(calculator.due_at(gio_vn(2026, 8, 3, 9, 0), 240))

        assert han == datetime(2026, 8, 3, 13, 0, tzinfo=VN)
        assert han.time() <= datetime(2026, 1, 1, 17, 30).time()

    def test_moi_han_deu_roi_vao_gio_hanh_chinh(self, calculator):
        """Quét cả tuần, mọi giờ: hạn SLA không bao giờ được nằm ngoài
        8:30–17:30 và không bao giờ rơi vào thứ Bảy hay Chủ nhật."""
        for ngay in range(27, 32):  # thứ Hai 27/07 → thứ Sáu 31/07
            for gio in range(0, 24, 3):
                han = xem_theo_gio_vn(calculator.due_at(gio_vn(2026, 7, ngay, gio, 0), 240))

                assert han.weekday() < 5, f"hạn rơi vào cuối tuần: {han}"
                assert (
                    datetime(2026, 1, 1, 8, 30).time()
                    <= han.time()
                    <= datetime(2026, 1, 1, 17, 30).time()
                ), f"hạn nằm ngoài giờ hành chính: {han}"

    def test_dau_vao_thieu_mui_gio_duoc_coi_la_UTC(self, calculator):
        """Bản ghi cũ lỡ mất tzinfo vẫn phải tính đúng, không được ngầm hiểu
        là giờ địa phương (sẽ lệch 7 tiếng)."""
        naive = datetime(2026, 7, 29, 2, 0)  # 02:00 UTC = 09:00 giờ VN
        ket_qua = calculator.due_at(naive, 120)

        assert xem_theo_gio_vn(ket_qua) == datetime(2026, 7, 29, 11, 0, tzinfo=VN)

    def test_tra_ve_dung_mui_gio_cua_dau_vao(self, calculator):
        ket_qua = calculator.due_at(gio_vn(2026, 7, 29, 9, 0), 120)
        assert ket_qua.tzinfo is UTC


class TestBusinessMinutesBetween:
    def test_trong_cung_mot_ngay_lam_viec(self, calculator):
        assert (
            calculator.business_minutes_between(
                gio_vn(2026, 7, 29, 9, 0), gio_vn(2026, 7, 29, 11, 30)
            )
            == 150
        )

    def test_KHONG_dem_thoi_gian_ngoai_gio(self, calculator):
        """Từ 17:00 thứ Tư tới 9:00 thứ Năm là 16 giờ đồng hồ, nhưng chỉ có
        30 phút cuối thứ Tư cộng 30 phút đầu thứ Năm là giờ làm việc."""
        assert (
            calculator.business_minutes_between(
                gio_vn(2026, 7, 29, 17, 0), gio_vn(2026, 7, 30, 9, 0)
            )
            == 60
        )

    def test_KHONG_dem_cuoi_tuan(self, calculator):
        """Cả thứ Bảy và Chủ nhật cộng lại phải bằng 0 phút làm việc."""
        assert (
            calculator.business_minutes_between(gio_vn(2026, 8, 1, 0, 0), gio_vn(2026, 8, 3, 0, 0))
            == 0
        )

    def test_KHONG_dem_ngay_le(self, calculator):
        # 02/09 là lễ ⇒ khoảng từ 01/09 17:30 tới 03/09 8:30 không có phút nào
        assert (
            calculator.business_minutes_between(
                gio_vn(2026, 9, 1, 17, 30), gio_vn(2026, 9, 3, 8, 30)
            )
            == 0
        )

    def test_dao_chieu_tra_ve_0(self, calculator):
        assert (
            calculator.business_minutes_between(
                gio_vn(2026, 7, 30, 9, 0), gio_vn(2026, 7, 29, 9, 0)
            )
            == 0
        )


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
