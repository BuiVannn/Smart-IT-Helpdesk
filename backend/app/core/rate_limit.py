"""Đếm số lần thử hỏng trong một khoảng thời gian — dùng cho đăng nhập (US-02).

★ VÌ SAO ƯU TIÊN REDIS, KHÔNG DÙNG BIẾN TOÀN CỤC:
API chạy nhiều worker (uvicorn --workers, hoặc nhiều container). Bộ đếm nằm
trong RAM của tiến trình này thì tiến trình kia không nhìn thấy — kẻ dò mật
khẩu chỉ cần thử đủ nhiều lần là rơi vào worker chưa đếm, và giới hạn coi như
không tồn tại. Redis là nơi duy nhất mọi worker cùng nhìn thấy.

Khi không có Redis (chạy test, chạy máy cá nhân) thì lùi về bộ đếm trong RAM:
hành vi giống hệt, chỉ khác là không chia sẻ giữa các tiến trình. Đây là đánh
đổi CÓ Ý THỨC để test không phải dựng thêm hạ tầng, không phải chỗ để quên.
"""

import threading
import time
from typing import Protocol

from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AttemptStore(Protocol):
    """Kho đếm. Cửa sổ cố định (fixed window) — đủ cho mục đích chống dò mật khẩu."""

    def incr(self, key: str, window_seconds: int) -> int:
        """Tăng bộ đếm, trả về giá trị sau khi tăng."""
        ...

    def peek(self, key: str) -> int:
        """Đọc bộ đếm mà KHÔNG tăng — dùng để kiểm tra trước khi thử mật khẩu."""
        ...

    def seconds_left(self, key: str) -> int: ...

    def reset(self, key: str) -> None: ...


class MemoryAttemptStore:
    """Bộ đếm trong RAM. Có khoá vì uvicorn chạy nhiều luồng trong một tiến trình."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def incr(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        with self._lock:
            count, expires_at = self._data.get(key, (0, 0.0))
            if expires_at <= now:            # cửa sổ cũ đã hết hạn ⇒ đếm lại từ đầu
                count, expires_at = 0, now + window_seconds
            count += 1
            self._data[key] = (count, expires_at)
            return count

    def peek(self, key: str) -> int:
        with self._lock:
            count, expires_at = self._data.get(key, (0, 0.0))
        return count if expires_at > time.monotonic() else 0

    def seconds_left(self, key: str) -> int:
        with self._lock:
            _, expires_at = self._data.get(key, (0, 0.0))
        return max(0, int(expires_at - time.monotonic()))

    def reset(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RedisAttemptStore:
    def __init__(self, client) -> None:
        self.client = client

    def incr(self, key: str, window_seconds: int) -> int:
        count = int(self.client.incr(key))
        if count == 1:
            # Chỉ đặt hạn ở lần đầu — nếu đặt lại mỗi lần thì kẻ tấn công cứ
            # thử liên tục là cửa sổ không bao giờ hết hạn, khoá vĩnh viễn.
            self.client.expire(key, window_seconds)
        return count

    def peek(self, key: str) -> int:
        raw = self.client.get(key)
        return int(raw) if raw else 0

    def seconds_left(self, key: str) -> int:
        return max(0, int(self.client.ttl(key) or 0))

    def reset(self, key: str) -> None:
        self.client.delete(key)


class AttemptLimiter:
    def __init__(
        self,
        store: AttemptStore,
        *,
        max_attempts: int,
        window_seconds: int,
        prefix: str,
    ) -> None:
        self.store = store
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.prefix = prefix

    def _key(self, identifier: str) -> str:
        return f"{self.prefix}:{identifier.strip().lower()}"

    def raise_if_blocked(self, identifier: str) -> None:
        """Gọi TRƯỚC khi kiểm tra mật khẩu.

        Phải chặn kể cả khi mật khẩu đúng (AC của US-02): nếu tài khoản đang bị
        khoá tạm mà mật khẩu đúng vẫn cho vào, kẻ tấn công dò được mật khẩu rồi
        thì giới hạn chẳng ngăn được gì.
        """
        key = self._key(identifier)
        if self.store.peek(key) < self.max_attempts:
            return
        seconds = self.store.seconds_left(key) or self.window_seconds
        minutes = max(1, round(seconds / 60))
        raise RateLimitError(
            f"Bạn đã thử quá nhiều lần. Vui lòng thử lại sau {minutes} phút.",
            headers={"Retry-After": str(seconds)},
        )

    def record(self, identifier: str) -> int:
        """Ghi nhận một lần dùng hạn mức. Trả về số lần đã dùng trong cửa sổ."""
        return self.store.incr(self._key(identifier), self.window_seconds)

    def record_failure(self, identifier: str) -> int:
        """Bí danh của `record()` cho ngữ cảnh đăng nhập, nơi thứ được đếm là
        số lần THẤT BẠI. Chỗ khác (ví dụ hạn mức gọi LLM) đếm số lần DÙNG —
        cùng cơ chế, khác ý nghĩa, nên gọi đúng tên để đọc code không hiểu nhầm."""
        return self.record(identifier)

    def reset(self, identifier: str) -> None:
        """Gọi khi đăng nhập thành công — chuỗi thất bại đã bị cắt."""
        self.store.reset(self._key(identifier))


def build_attempt_store() -> AttemptStore:
    """Dùng Redis nếu kết nối được, không thì lùi về RAM.

    Kiểm tra kết nối NGAY tại đây thay vì để lỗi nổ ở lần đăng nhập đầu tiên —
    thà biết lúc khởi động còn hơn biết lúc người dùng đang đăng nhập.
    """
    try:
        import redis

        from app.core.config import settings

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        logger.info("giới hạn đăng nhập: dùng Redis")
        return RedisAttemptStore(client)
    except Exception as exc:
        logger.warning(
            "giới hạn đăng nhập: KHÔNG kết nối được Redis, lùi về bộ đếm trong RAM "
            f"(không chia sẻ giữa các worker) — {type(exc).__name__}: {exc}"
        )
        return MemoryAttemptStore()
