"""Kiểm soát chi phí LLM.

Chặn cứng theo ngân sách là YÊU CẦU BẮT BUỘC, không phải tuỳ chọn: một
vòng lặp lỗi gọi LLM liên tục có thể đốt hết ngân sách của cả dự án trong
một đêm.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import settings
from app.core.exceptions import BudgetExceededError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Giá tham khảo USD / 1M token. Cập nhật theo provider thực tế.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "fake-model": (0.0, 0.0),
    "fake-embedding": (0.0, 0.0),
}

WARN_RATIO = 0.8


@dataclass
class UsageRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def cost_usd(self) -> float:
        in_price, out_price = PRICING.get(self.model, (0.5, 1.5))
        return (self.prompt_tokens * in_price + self.completion_tokens * out_price) / 1_000_000


class CostGuard:
    """Theo dõi chi phí trong tháng. Bản đơn giản giữ trong bộ nhớ.

    TODO(sau khi có bảng ai_usage): đọc tổng chi phí từ database thay vì
    biến trong bộ nhớ, để nhiều worker cùng thấy một con số.
    """

    def __init__(self, monthly_budget_usd: float | None = None) -> None:
        self.monthly_budget = monthly_budget_usd or settings.AI_MONTHLY_BUDGET_USD
        self._spent: float = 0.0
        self._month = datetime.now(UTC).strftime("%Y-%m")
        self._warned = False

    def _reset_if_new_month(self) -> None:
        current = datetime.now(UTC).strftime("%Y-%m")
        if current != self._month:
            self._month, self._spent, self._warned = current, 0.0, False

    @property
    def spent_usd(self) -> float:
        self._reset_if_new_month()
        return self._spent

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.monthly_budget - self.spent_usd)

    def check_budget(self) -> None:
        """Gọi TRƯỚC mỗi lời gọi LLM. Ném BudgetExceededError khi hết ngân sách."""
        self._reset_if_new_month()
        if self._spent >= self.monthly_budget:
            raise BudgetExceededError(
                f"Đã dùng hết ngân sách AI tháng này "
                f"({self._spent:.2f}/{self.monthly_budget:.2f} USD)"
            )

    def record(self, usage: UsageRecord) -> float:
        self._reset_if_new_month()
        cost = usage.cost_usd
        self._spent += cost
        ratio = self._spent / self.monthly_budget if self.monthly_budget else 0
        if ratio >= WARN_RATIO and not self._warned:
            self._warned = True
            logger.warning(
                f"Đã dùng {ratio:.0%} ngân sách AI tháng này",
                extra={"extra_fields": {"spent_usd": round(self._spent, 4)}},
            )
        return cost


cost_guard = CostGuard()
