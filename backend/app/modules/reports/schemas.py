"""Schema của module báo cáo.

`ai-accuracy` (US-22) thuộc F3; phần còn lại là F7 — dashboard vận hành:
`/reports/overview` (US-37), `/reports/resolution-time` (US-38),
`/reports/agent-workload` (US-39), `/reports/tickets/export` (US-40).

`/reports/satisfaction` (US-42) vẫn còn trống — nó thuộc F8, và chưa có
đường nào ghi vào bảng `ticket_ratings` nên báo cáo đó chưa có dữ liệu để
đọc. Bảng workload đã sẵn cột điểm hài lòng, sẽ tự có số khi F8 xong.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel


class RateBucket(ResponseModel):
    key: str
    label: str
    applied: int
    accepted: int
    corrected: int
    decided: int
    acceptance_rate: float | None = Field(default=None, serialization_alias="acceptanceRate")


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
    acceptance_rate: float | None = Field(default=None, serialization_alias="acceptanceRate")
    low_confidence_rate: float | None = Field(default=None, serialization_alias="lowConfidenceRate")
    failure_rate: float | None = Field(default=None, serialization_alias="failureRate")
    avg_latency_ms: int | None = Field(default=None, serialization_alias="avgLatencyMs")
    avg_confidence: float | None = Field(default=None, serialization_alias="avgConfidence")
    estimated_cost_usd: float = Field(serialization_alias="estimatedCostUsd")

    status_breakdown: dict[str, int] = Field(serialization_alias="statusBreakdown")
    by_category: list[RateBucket] = Field(serialization_alias="byCategory")
    by_week: list[RateBucket] = Field(serialization_alias="byWeek")
    confusion: list[ConfusionCellResponse]

    generated_at: datetime = Field(serialization_alias="generatedAt")
    cached: bool = False


# ── F7 — Dashboard vận hành ───────────────────────────────────────────


class CountBucketResponse(ResponseModel):
    """Một cột trong biểu đồ. `label` là tiếng Việt sẵn sàng để vẽ."""

    key: str
    label: str
    count: int


class OverviewResponse(ResponseModel):
    """US-37 — con số để trả lời "đội IT đang thế nào" trong một màn hình."""

    from_at: datetime = Field(serialization_alias="from")
    to_at: datetime = Field(serialization_alias="to")
    total: int
    open_total: int = Field(serialization_alias="openTotal")
    resolved_total: int = Field(serialization_alias="resolvedTotal")
    breached_total: int = Field(serialization_alias="breachedTotal")
    unassigned_total: int = Field(serialization_alias="unassignedTotal")
    breach_rate: float | None = Field(default=None, serialization_alias="breachRate")
    by_status: list[CountBucketResponse] = Field(serialization_alias="byStatus")
    by_priority: list[CountBucketResponse] = Field(serialization_alias="byPriority")
    by_category: list[CountBucketResponse] = Field(serialization_alias="byCategory")
    daily: list[CountBucketResponse]
    generated_at: datetime = Field(serialization_alias="generatedAt")
    cached: bool = False


class DurationRowResponse(ResponseModel):
    """US-38 — một loại sự cố. Đơn vị là PHÚT, ghi rõ trong tên field để
    frontend không phải đoán và không ai chia nhầm 60 lần."""

    key: str
    label: str
    tickets: int
    first_response_p50_minutes: float | None = Field(
        default=None, serialization_alias="firstResponseP50Minutes"
    )
    first_response_p90_minutes: float | None = Field(
        default=None, serialization_alias="firstResponseP90Minutes"
    )
    resolution_p50_minutes: float | None = Field(
        default=None, serialization_alias="resolutionP50Minutes"
    )
    resolution_p90_minutes: float | None = Field(
        default=None, serialization_alias="resolutionP90Minutes"
    )


class ResolutionTimeResponse(ResponseModel):
    from_at: datetime = Field(serialization_alias="from")
    to_at: datetime = Field(serialization_alias="to")
    rows: list[DurationRowResponse]
    generated_at: datetime = Field(serialization_alias="generatedAt")


class AgentWorkloadRowResponse(ResponseModel):
    """US-39 — một IT Agent."""

    agent_id: UUID = Field(serialization_alias="agentId")
    agent_name: str = Field(serialization_alias="agentName")
    open_tickets: int = Field(serialization_alias="openTickets")
    urgent_open: int = Field(serialization_alias="urgentOpen")
    resolved_in_period: int = Field(serialization_alias="resolvedInPeriod")
    avg_resolution_minutes: float | None = Field(
        default=None, serialization_alias="avgResolutionMinutes"
    )
    sla_breached: int = Field(serialization_alias="slaBreached")
    sla_breach_rate: float | None = Field(default=None, serialization_alias="slaBreachRate")
    avg_rating: float | None = Field(default=None, serialization_alias="avgRating")
    rating_count: int = Field(serialization_alias="ratingCount")


class AgentWorkloadResponse(ResponseModel):
    from_at: datetime = Field(serialization_alias="from")
    to_at: datetime = Field(serialization_alias="to")
    rows: list[AgentWorkloadRowResponse]
    generated_at: datetime = Field(serialization_alias="generatedAt")


# ── F8 — Đánh giá sau xử lý (US-42) ────────────────────────────────────


class SatisfactionBucketResponse(ResponseModel):
    """Một dòng: toàn hệ thống, một Agent, một loại sự cố, hoặc một tháng.

    `responseRate` là `null` khi kỳ báo cáo chưa có ticket nào đã đóng —
    KHÁC với 0 (đã đóng nhiều ticket nhưng không ai đánh giá). `avgScore`
    luôn đi kèm `ratingCount`/`responseRate`: điểm cao mà tỉ lệ phản hồi
    thấp thì không đáng tin (US-42, AC 2), frontend phải hiển thị cả hai.
    """

    key: str
    label: str
    rating_count: int = Field(serialization_alias="ratingCount")
    avg_score: float | None = Field(default=None, serialization_alias="avgScore")
    distribution: dict[str, int]
    closed_tickets: int = Field(serialization_alias="closedTickets")
    response_rate: float | None = Field(default=None, serialization_alias="responseRate")


class SatisfactionResponse(ResponseModel):
    """US-42 — dữ liệu cho báo cáo hiệu suất đội IT theo điểm hài lòng."""

    from_at: datetime = Field(serialization_alias="from")
    to_at: datetime = Field(serialization_alias="to")
    overall: SatisfactionBucketResponse
    by_agent: list[SatisfactionBucketResponse] = Field(serialization_alias="byAgent")
    by_category: list[SatisfactionBucketResponse] = Field(serialization_alias="byCategory")
    by_month: list[SatisfactionBucketResponse] = Field(serialization_alias="byMonth")
    generated_at: datetime = Field(serialization_alias="generatedAt")
