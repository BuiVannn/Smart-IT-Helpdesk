"""Schema của module báo cáo.

★ CÒN TRỐNG, THUỘC VỀ NGƯỜI KHÁC — đừng viết chồng lên. Hiện chỉ có
`ai-accuracy` (US-22). Các báo cáo còn lại là của Trần Tiến Dũng:
`/reports/overview` (US-37), `/reports/resolution-time` (US-38),
`/reports/agent-workload` (US-39), `/reports/tickets/export` (US-40),
`/reports/satisfaction` (US-42).
"""

from datetime import datetime

from pydantic import Field

from app.core.schemas import ResponseModel


class RateBucket(ResponseModel):
    key: str
    label: str
    applied: int
    accepted: int
    corrected: int
    decided: int
    acceptance_rate: float | None = Field(
        default=None, serialization_alias="acceptanceRate"
    )


class ConfusionCellResponse(ResponseModel):
    ai_category: str = Field(serialization_alias="aiCategory")
    final_category: str = Field(serialization_alias="finalCategory")
    count: int


class AiAccuracyResponse(ResponseModel):
    """US-22 — số liệu để trả lời "AI phân loại có dùng được không?".

    `acceptanceRate` là `null` chứ KHÔNG phải 0 khi chưa có ticket nào được
    chốt. 0 nghĩa là "AI sai tất"; null nghĩa là "chưa đủ dữ liệu để nói" —
    hai điều hoàn toàn khác nhau, và trong tuần đầu chạy thì luôn là vế sau.
    """

    from_at: datetime = Field(serialization_alias="from")
    to_at: datetime = Field(serialization_alias="to")

    total_runs: int = Field(serialization_alias="totalRuns")
    applied: int
    accepted: int
    corrected: int
    decided: int
    acceptance_rate: float | None = Field(
        default=None, serialization_alias="acceptanceRate"
    )
    low_confidence_rate: float | None = Field(
        default=None, serialization_alias="lowConfidenceRate"
    )
    failure_rate: float | None = Field(default=None, serialization_alias="failureRate")
    avg_latency_ms: int | None = Field(default=None, serialization_alias="avgLatencyMs")
    avg_confidence: float | None = Field(
        default=None, serialization_alias="avgConfidence"
    )
    estimated_cost_usd: float = Field(serialization_alias="estimatedCostUsd")

    status_breakdown: dict[str, int] = Field(serialization_alias="statusBreakdown")
    by_category: list[RateBucket] = Field(serialization_alias="byCategory")
    by_week: list[RateBucket] = Field(serialization_alias="byWeek")
    confusion: list[ConfusionCellResponse]

    generated_at: datetime = Field(serialization_alias="generatedAt")
    cached: bool = False
