"""Cache ngắn hạn cho báo cáo (US-37 — "kết quả cache 5 phút, có ?refresh=true").

★ HỎNG CACHE KHÔNG ĐƯỢC LÀM HỎNG BÁO CÁO. Redis ở đây là tối ưu, không phải
phụ thuộc: mọi lỗi kết nối, lỗi giải mã, lỗi kiểu dữ liệu đều rơi về "tính
lại từ database". Một dashboard chậm hơn 200 ms vẫn tốt hơn một dashboard trả
lỗi 500 vì Redis đang khởi động lại.

Khác với `core/rate_limit.py`, ở đây KHÔNG dò kết nối một lần lúc import rồi
nhớ mãi: cache dựng client lười và thử lại ở mỗi lần dùng, nên Redis lên lại
sau sự cố là cache tự hoạt động trở lại mà không cần restart tiến trình.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 300  # 5 phút, đúng con số trong AC của US-37
KEY_PREFIX = "report:"

_client: Any | None = None
_client_failed = False


def _get_client() -> Any | None:
    """Dựng client Redis khi cần. Trả `None` nếu không dùng được."""
    global _client, _client_failed

    if _client is not None:
        return _client
    if _client_failed:
        # Đã hỏng ở lần trước — vẫn thử lại, nhưng không log lặp lại nữa.
        _client_failed = False

    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        client.ping()
        _client = client
        return client
    except Exception as exc:
        _client_failed = True
        logger.debug(f"cache báo cáo: không dùng được Redis — {type(exc).__name__}: {exc}")
        return None


def _drop_client() -> None:
    global _client
    _client = None


def window_key(prefix: str, start: datetime, end: datetime, ttl: int = CACHE_TTL_SECONDS) -> str:
    """Khoá cache cho một khoảng thời gian, LÀM TRÒN XUỐNG theo bước `ttl`.

    ★ ĐÂY LÀ CHỖ ĐÃ HỎNG MỘT LẦN, đừng bỏ bước làm tròn.

    Dashboard gọi `/reports/overview` không kèm `from`/`to`, nên khoảng thời
    gian mặc định được tính từ `datetime.now()` — chính xác tới micro giây.
    Ghép thẳng mốc đó vào khoá thì MỖI REQUEST MỘT KHOÁ MỚI: cache ghi đều
    đặn, TTL 300 giây đàng hoàng, nhưng không bao giờ trúng. Chạy thử trên
    server thật mới lộ ra — `cached` luôn `false` trong khi Redis phình lên
    một khoá mỗi lần tải trang.

    Làm tròn xuống theo đúng bước TTL biến "cache 5 phút" thành sự thật:
    mọi request trong cùng một khung 5 phút dùng chung một khoá.
    """

    def khung(moment: datetime) -> int:
        giay = int(moment.timestamp())
        return giay - (giay % ttl)

    return f"{prefix}:{khung(start)}:{khung(end)}"


def get(key: str) -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(KEY_PREFIX + key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug(f"cache báo cáo: đọc hỏng — {type(exc).__name__}: {exc}")
        _drop_client()
        return None


def set(key: str, value: dict, ttl: int = CACHE_TTL_SECONDS) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        # `default=str` để datetime/UUID đi qua được mà không phải viết encoder
        # riêng. Giá trị chỉ dùng để trả lại nguyên văn cho client, không dùng
        # để tính toán tiếp, nên chuỗi hoá là đủ.
        client.setex(KEY_PREFIX + key, ttl, json.dumps(value, default=str, ensure_ascii=False))
    except Exception as exc:
        logger.debug(f"cache báo cáo: ghi hỏng — {type(exc).__name__}: {exc}")
        _drop_client()
