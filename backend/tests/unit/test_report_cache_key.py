"""Khoá cache báo cáo (US-37 — "kết quả cache 5 phút").

★ VÌ SAO CÓ FILE NÀY: bản đầu tiên ghép thẳng `datetime.now().isoformat()`
vào khoá cache. Cache ghi đều, TTL đúng 300 giây, endpoint trả 200 — và test
API cũ vẫn xanh vì nó chỉ khẳng định mã trạng thái. Nhưng mỗi request sinh
MỘT KHOÁ MỚI nên cache không bao giờ trúng, còn Redis thì phình lên một khoá
mỗi lần tải trang. Chỉ chạy server thật mới thấy `cached` luôn `false`.

Test dưới đây khẳng định đúng tính chất đã hỏng, ở dạng thuần — không cần
Redis, nên nó chạy cả trong CI nơi không có Redis.
"""

from datetime import UTC, datetime, timedelta

from app.modules.reports.cache import CACHE_TTL_SECONDS, window_key

MOC = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)


class TestKhoaCacheTheoKhungThoiGian:
    def test_hai_request_cach_nhau_vai_giay_dung_CHUNG_mot_khoa(self):
        """Đây chính là lỗi đã xảy ra. Dashboard không truyền `from`/`to`, nên
        khoảng thời gian được tính từ `now()` — hai lần tải trang cách nhau
        vài giây cho hai mốc khác nhau tới micro giây."""
        a = window_key("overview", MOC - timedelta(days=30), MOC)
        b = window_key(
            "overview",
            MOC - timedelta(days=30) + timedelta(seconds=3, microseconds=417),
            MOC + timedelta(seconds=3, microseconds=417),
        )

        assert a == b

    def test_qua_khung_TTL_thi_doi_khoa(self):
        """Hết 5 phút phải tính lại — nếu không thì "cache 5 phút" thành
        "cache vĩnh viễn"."""
        a = window_key("overview", MOC - timedelta(days=30), MOC)
        b = window_key(
            "overview",
            MOC - timedelta(days=30),
            MOC + timedelta(seconds=CACHE_TTL_SECONDS),
        )

        assert a != b

    def test_khoang_thoi_gian_khac_nhau_KHONG_dung_chung_khoa(self):
        """7 ngày và 30 ngày là hai báo cáo khác nhau — dùng chung khoá là
        trả sai số liệu, tệ hơn nhiều so với không cache."""
        bay_ngay = window_key("overview", MOC - timedelta(days=7), MOC)
        ba_muoi_ngay = window_key("overview", MOC - timedelta(days=30), MOC)

        assert bay_ngay != ba_muoi_ngay

    def test_tien_to_khac_nhau_KHONG_dung_chung_khoa(self):
        assert window_key("overview", MOC, MOC) != window_key("workload", MOC, MOC)

    def test_khoa_on_dinh_qua_nhieu_lan_goi(self):
        khoang = (MOC - timedelta(days=30), MOC)
        assert len({window_key("overview", *khoang) for _ in range(5)}) == 1
