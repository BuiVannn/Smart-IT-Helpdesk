"""Timeout, retry có jitter, circuit breaker cho các lời gọi ra bên ngoài.

VÌ SAO PHẢI CÓ JITTER: không có jitter, mọi worker gặp lỗi cùng lúc sẽ thử
lại cùng lúc — tự tạo ra một đợt tấn công vào chính provider đang gặp sự cố.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

RETRYABLE = (TimeoutError, ConnectionError, asyncio.TimeoutError)


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 2.0
    multiplier: float = 3.0
    jitter: float = 0.3  # ±30%


async def with_retry[T](
    func: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
    *,
    operation: str = "external_call",
) -> T:
    cfg = config or RetryConfig()
    last_error: Exception | None = None

    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await func()
        except RETRYABLE as exc:
            last_error = exc
            if attempt == cfg.max_attempts:
                break
            delay = cfg.base_delay * (cfg.multiplier ** (attempt - 1))
            delay *= 1 + random.uniform(-cfg.jitter, cfg.jitter)  # noqa: S311
            logger.warning(
                f"{operation} lỗi lần {attempt}/{cfg.max_attempts}, thử lại sau {delay:.1f}s",
                extra={"extra_fields": {"error": str(exc)}},
            )
            await asyncio.sleep(delay)
        except Exception as exc:
            # Lỗi KHÔNG tạm thời (400, 401...) — thử lại cũng vô ích
            raise ExternalServiceError(f"{operation} thất bại: {type(exc).__name__}") from exc

    raise ExternalServiceError(
        f"{operation} thất bại sau {cfg.max_attempts} lần thử"
    ) from last_error


@dataclass
class CircuitBreaker:
    """Sau N lỗi liên tiếp thì MỞ MẠCH — fail ngay, không gọi mạng nữa.

    Bảo vệ cả provider (không bị hammer khi đang hỏng) lẫn worker của mình
    (không tốn thời gian chờ những lời gọi chắc chắn thất bại).
    """

    failure_threshold: int = 5
    recovery_seconds: float = 60.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.recovery_seconds:
            self._opened_at = None  # sang trạng thái half-open: cho thử 1 lần
            self._failures = 0
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            logger.error(f"Circuit breaker MỞ sau {self._failures} lỗi liên tiếp")

    async def call[T](self, func: Callable[[], Awaitable[T]], *, operation: str = "call") -> T:
        if self.is_open:
            raise ExternalServiceError(
                f"{operation}: dịch vụ đang tạm ngưng do lỗi liên tục, thử lại sau"
            )
        try:
            result = await func()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
