"""Unit test cho bộ đếm số lần thử — lớp thuần, không cần DB, không cần Redis."""

import pytest

from app.core.exceptions import RateLimitError
from app.core.rate_limit import AttemptLimiter, MemoryAttemptStore


@pytest.fixture
def limiter() -> AttemptLimiter:
    return AttemptLimiter(
        MemoryAttemptStore(), max_attempts=3, window_seconds=900, prefix="thu"
    )


def test_chua_that_bai_lan_nao_thi_khong_chan(limiter):
    limiter.raise_if_blocked("a@company.com")   # không được ném lỗi


def test_chan_khi_dat_nguong(limiter):
    for _ in range(3):
        limiter.record_failure("a@company.com")

    with pytest.raises(RateLimitError):
        limiter.raise_if_blocked("a@company.com")


def test_duoi_nguong_thi_van_cho_qua(limiter):
    for _ in range(2):
        limiter.record_failure("a@company.com")
    limiter.raise_if_blocked("a@company.com")


def test_bo_dem_tach_rieng_theo_tung_email(limiter):
    """Người này bị khoá không được kéo theo người khác — nếu chung bộ đếm thì
    chỉ cần dò sai 3 lần là khoá được tài khoản của bất kỳ ai (DoS)."""
    for _ in range(3):
        limiter.record_failure("nan-nhan@company.com")

    limiter.raise_if_blocked("nguoi-khac@company.com")


def test_khong_phan_biet_hoa_thuong(limiter):
    """Nếu phân biệt, kẻ tấn công chỉ cần đổi kiểu chữ là có thêm 3 lần thử."""
    for _ in range(3):
        limiter.record_failure("A@Company.com")

    with pytest.raises(RateLimitError):
        limiter.raise_if_blocked("a@company.com")


def test_reset_xoa_chuoi_that_bai(limiter):
    for _ in range(3):
        limiter.record_failure("a@company.com")
    limiter.reset("a@company.com")

    limiter.raise_if_blocked("a@company.com")


def test_loi_kem_header_Retry_After(limiter):
    for _ in range(3):
        limiter.record_failure("a@company.com")

    with pytest.raises(RateLimitError) as exc:
        limiter.raise_if_blocked("a@company.com")

    assert int(exc.value.headers["Retry-After"]) > 0


def test_cua_so_het_han_thi_dem_lai_tu_dau():
    """Cửa sổ 0 giây ⇒ hết hạn ngay. Không có bước này thì tài khoản bị khoá
    vĩnh viễn sau 3 lần gõ nhầm."""
    limiter = AttemptLimiter(
        MemoryAttemptStore(), max_attempts=3, window_seconds=0, prefix="thu"
    )
    for _ in range(3):
        limiter.record_failure("a@company.com")

    limiter.raise_if_blocked("a@company.com")
