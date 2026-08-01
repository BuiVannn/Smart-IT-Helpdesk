"""Endpoint báo cáo.

★ CÒN TRỐNG, THUỘC VỀ TRẦN TIẾN DŨNG — đừng viết chồng lên:
`/reports/overview` (US-37), `/reports/resolution-time` (US-38),
`/reports/agent-workload` (US-39), `/reports/tickets/export` (US-40),
`/reports/satisfaction` (US-42), `/reports/sla-compliance`.

Hiện chỉ có `ai-accuracy` vì nó là chỉ số của F3.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_agent
from app.db.session import get_db
from app.modules.reports.schemas import (
    AiAccuracyResponse,
    ConfusionCellResponse,
    RateBucket,
)
from app.modules.reports.service import AiAccuracyService
from app.modules.users.models import User

router = APIRouter()


@router.get(
    "/ai-accuracy",
    response_model=AiAccuracyResponse,
    summary="Độ chính xác phân loại của AI theo tuần và theo loại sự cố (US-22)",
)
def ai_accuracy(
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    _: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> AiAccuracyResponse:
    """Mặc định 30 ngày gần nhất. Chỉ IT Agent và Admin xem được."""
    report = AiAccuracyService(db).report(from_at=from_at, to_at=to_at)

    return AiAccuracyResponse(
        from_at=report.from_at,
        to_at=report.to_at,
        total_runs=report.total_runs,
        applied=report.applied,
        accepted=report.accepted,
        corrected=report.corrected,
        decided=report.decided,
        acceptance_rate=report.acceptance_rate,
        low_confidence_rate=report.low_confidence_rate,
        failure_rate=report.failure_rate,
        avg_latency_ms=report.avg_latency_ms,
        avg_confidence=report.avg_confidence,
        estimated_cost_usd=report.estimated_cost_usd,
        status_breakdown=report.status_breakdown,
        by_category=[_bucket(b) for b in report.by_category],
        by_week=[_bucket(b) for b in report.by_week],
        confusion=[
            ConfusionCellResponse(
                ai_category=c.ai_category, final_category=c.final_category, count=c.count
            )
            for c in report.confusion
        ],
        generated_at=datetime.now(UTC),
        # Chưa cache — ở quy mô này (vài trăm bản ghi) truy vấn dưới 50 ms.
        # Thêm cache khi báo cáo chậm thật, không phải vì "báo cáo thì phải cache".
        cached=False,
    )


def _bucket(bucket) -> RateBucket:
    return RateBucket(
        key=bucket.key,
        label=bucket.label,
        applied=bucket.applied,
        accepted=bucket.accepted,
        corrected=bucket.corrected,
        decided=bucket.decided,
        acceptance_rate=bucket.acceptance_rate,
    )
