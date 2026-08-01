"""Báo cáo độ chính xác của AI phân loại (US-22).

VÌ SAO BÁO CÁO NÀY QUAN TRỌNG HƠN VẺ NGOÀI CỦA NÓ: không có số đo thì mọi
thay đổi prompt chỉ là cảm tính. `ai_classifications` ghi lại mọi lượt phân
loại kể cả thất bại; file này là chỗ duy nhất biến đống bản ghi đó thành câu
trả lời cho "đổi prompt xong tốt lên hay xấu đi?".

Ngưỡng cảnh báo vận hành (docs/design/07 §5.3): tỉ lệ Agent sửa lại > 40%
trong 7 ngày, hoặc tỉ lệ FAILED > 10% trong 1 giờ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.cost_guard import PRICING
from app.modules.tickets.constants import AiStatus
from app.modules.tickets.models import AiClassification, Ticket, TicketCategory

DEFAULT_WINDOW_DAYS = 30


@dataclass
class Bucket:
    """Một dòng trong bảng chia theo loại sự cố hoặc theo tuần."""

    key: str
    label: str
    applied: int = 0
    accepted: int = 0
    corrected: int = 0

    @property
    def decided(self) -> int:
        """Mẫu số CHỈ gồm các lượt đã có kết luận.

        Ticket còn đang mở thì chưa ai kết luận AI đúng hay sai. Đưa chúng vào
        mẫu số sẽ kéo tỉ lệ chấp nhận xuống thấp giả tạo, và tỉ lệ ấy sẽ tự
        "cải thiện" mỗi khi có ticket được đóng — một chỉ số như vậy vô dụng.
        """
        return self.accepted + self.corrected

    @property
    def acceptance_rate(self) -> float | None:
        return round(self.accepted / self.decided, 4) if self.decided else None


@dataclass
class ConfusionCell:
    ai_category: str
    final_category: str
    count: int


@dataclass
class AiAccuracyReport:
    from_at: datetime
    to_at: datetime
    total_runs: int = 0
    applied: int = 0
    accepted: int = 0
    corrected: int = 0
    avg_latency_ms: int | None = None
    avg_confidence: float | None = None
    estimated_cost_usd: float = 0.0
    status_breakdown: dict[str, int] = field(default_factory=dict)
    by_category: list[Bucket] = field(default_factory=list)
    by_week: list[Bucket] = field(default_factory=list)
    confusion: list[ConfusionCell] = field(default_factory=list)

    @property
    def decided(self) -> int:
        return self.accepted + self.corrected

    @property
    def acceptance_rate(self) -> float | None:
        return round(self.accepted / self.decided, 4) if self.decided else None

    @property
    def low_confidence_rate(self) -> float | None:
        return self._status_rate(AiStatus.LOW_CONFIDENCE)

    @property
    def failure_rate(self) -> float | None:
        return self._status_rate(AiStatus.FAILED)

    def _status_rate(self, status: AiStatus) -> float | None:
        total = sum(self.status_breakdown.values())
        return round(self.status_breakdown.get(str(status), 0) / total, 4) if total else None


class AiAccuracyService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def report(
        self, *, from_at: datetime | None = None, to_at: datetime | None = None
    ) -> AiAccuracyReport:
        end = to_at or datetime.now(UTC)
        start = from_at or end - timedelta(days=DEFAULT_WINDOW_DAYS)
        report = AiAccuracyReport(from_at=start, to_at=end)

        self._load_totals(report)
        self._load_status_breakdown(report)
        self._load_cost(report)
        report.by_category = self._load_by_category(report)
        report.by_week = self._load_by_week(report)
        report.confusion = self._load_confusion(report)
        return report

    # ── Truy vấn ──────────────────────────────────────────────────────

    def _window(self, report: AiAccuracyReport):
        return (
            AiClassification.created_at >= report.from_at,
            AiClassification.created_at <= report.to_at,
        )

    def _load_totals(self, report: AiAccuracyReport) -> None:
        row = self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(AiClassification.was_applied.is_(True)).label("applied"),
                func.count().filter(AiClassification.was_accepted.is_(True)).label("accepted"),
                func.count().filter(AiClassification.was_accepted.is_(False)).label("corrected"),
                func.avg(AiClassification.latency_ms).label("latency"),
                func.avg(AiClassification.confidence).label("confidence"),
            )
            .select_from(AiClassification)
            .where(*self._window(report))
        ).mappings().one()

        report.total_runs = int(row["total"])
        report.applied = int(row["applied"])
        report.accepted = int(row["accepted"])
        report.corrected = int(row["corrected"])
        report.avg_latency_ms = int(row["latency"]) if row["latency"] is not None else None
        report.avg_confidence = (
            round(float(row["confidence"]), 4) if row["confidence"] is not None else None
        )

    def _load_status_breakdown(self, report: AiAccuracyReport) -> None:
        """Phân bố `ai_status` đọc từ chính bảng tickets.

        Không suy ra từ `ai_classifications`: một ticket có thể có nhiều lượt
        phân loại (job đối soát chạy lại), nên đếm ở đó sẽ đếm trùng ticket.
        `tickets.ai_status` mới là trạng thái cuối cùng, mỗi ticket một dòng.
        """
        rows = self.session.execute(
            select(Ticket.ai_status, func.count())
            .where(Ticket.created_at >= report.from_at, Ticket.created_at <= report.to_at)
            .group_by(Ticket.ai_status)
        ).all()
        report.status_breakdown = {str(status): int(count) for status, count in rows}

    def _load_cost(self, report: AiAccuracyReport) -> None:
        """Chi phí ước tính = Σ token × đơn giá của từng model.

        Cộng dồn theo model chứ không dùng một đơn giá chung: chạy song song
        `gpt-4o-mini` và đường dự phòng `rule-based` (miễn phí) mà tính chung
        một giá sẽ thổi phồng con số lên nhiều lần.
        """
        rows = self.session.execute(
            select(
                AiClassification.model_name,
                func.coalesce(func.sum(AiClassification.prompt_tokens), 0),
                func.coalesce(func.sum(AiClassification.completion_tokens), 0),
            )
            .where(*self._window(report))
            .group_by(AiClassification.model_name)
        ).all()

        total = 0.0
        for model_name, prompt_tokens, completion_tokens in rows:
            in_price, out_price = PRICING.get(model_name, (0.5, 1.5))
            total += (int(prompt_tokens) * in_price + int(completion_tokens) * out_price) / 1_000_000
        report.estimated_cost_usd = round(total, 6)

    def _load_by_category(self, report: AiAccuracyReport) -> list[Bucket]:
        rows = self.session.execute(
            select(
                TicketCategory.slug,
                TicketCategory.name,
                func.count(),
                func.count().filter(AiClassification.was_accepted.is_(True)),
                func.count().filter(AiClassification.was_accepted.is_(False)),
            )
            .select_from(AiClassification)
            .join(TicketCategory, TicketCategory.id == AiClassification.suggested_category_id)
            .where(*self._window(report), AiClassification.was_applied.is_(True))
            .group_by(TicketCategory.slug, TicketCategory.name)
            .order_by(func.count().desc())
        ).all()
        return [
            Bucket(key=slug, label=name, applied=int(applied),
                   accepted=int(accepted), corrected=int(corrected))
            for slug, name, applied, accepted, corrected in rows
        ]

    def _load_by_week(self, report: AiAccuracyReport) -> list[Bucket]:
        week = func.date_trunc("week", AiClassification.created_at).label("week")
        rows = self.session.execute(
            select(
                week,
                func.count(),
                func.count().filter(AiClassification.was_accepted.is_(True)),
                func.count().filter(AiClassification.was_accepted.is_(False)),
            )
            .select_from(AiClassification)
            .where(*self._window(report), AiClassification.was_applied.is_(True))
            .group_by(week)
            .order_by(week)
        ).all()
        return [
            Bucket(key=start.date().isoformat(), label=f"Tuần {start:%d/%m}",
                   applied=int(applied), accepted=int(accepted), corrected=int(corrected))
            for start, applied, accepted, corrected in rows
        ]

    def _load_confusion(self, report: AiAccuracyReport) -> list[ConfusionCell]:
        """Ma trận nhầm lẫn: loại AI gán ↔ loại cuối cùng của ticket.

        Đây là thứ chỉ ra prompt cần sửa ở đâu: "AI gán `software` nhưng thật
        ra là `access` 12 lần" cụ thể hơn nhiều so với "độ chính xác 78%".
        """
        ai_cat = TicketCategory.__table__.alias("ai_cat")
        final_cat = TicketCategory.__table__.alias("final_cat")

        rows = self.session.execute(
            select(ai_cat.c.name, final_cat.c.name, func.count())
            .select_from(AiClassification)
            .join(Ticket, Ticket.id == AiClassification.ticket_id)
            .join(ai_cat, ai_cat.c.id == AiClassification.suggested_category_id)
            .outerjoin(final_cat, final_cat.c.id == Ticket.category_id)
            .where(*self._window(report), AiClassification.was_applied.is_(True))
            .group_by(ai_cat.c.name, final_cat.c.name)
            .order_by(func.count().desc())
        ).all()

        return [
            ConfusionCell(
                ai_category=ai_name,
                final_category=final_name or "(chưa phân loại)",
                count=int(count),
            )
            for ai_name, final_name, count in rows
        ]
