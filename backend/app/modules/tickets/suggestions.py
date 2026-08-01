"""F3 — Gợi ý người xử lý theo chuyên môn và khối lượng công việc (US-20).

VÌ SAO KHÔNG DÙNG LLM Ở ĐÂY (docs/design/07 §2.4): đây là bài toán tính điểm
trên dữ liệu có cấu trúc. LLM sẽ chậm hơn, đắt hơn, không xác định, và không
kiểm thử được. Một hàm thuần cho kết quả tốt hơn, chạy trong micro-giây, và
có unit test phủ hết ca biên.

CHỈ GỢI Ý, KHÔNG TỰ GIAO. Con người vẫn ra quyết định ở phiên bản 1 — giao
sai một ticket URGENT cho người đang nghỉ phép tốn nhiều thời gian hơn toàn
bộ thời gian mà việc tự động giao tiết kiệm được. Tự động giao là `Could`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import Integer, case, func, literal, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.tickets.constants import OPEN_STATUSES, TicketPriority
from app.modules.tickets.models import Ticket, TicketCategory
from app.modules.tickets.sla import BusinessCalendar
from app.modules.users.constants import UserRole
from app.modules.users.models import AgentSkill, Holiday, User

MAX_SKILL_LEVEL = 3
OFF_DUTY_FACTOR = 0.3   # ngoài ca vẫn được xét, chỉ bị trừ điểm

# Trọng số tải theo mức ưu tiên: một ticket URGENT ngốn thời gian gấp nhiều
# lần một câu hỏi LOW, nên đếm đầu ticket là đếm sai.
PRIORITY_WEIGHT: dict[TicketPriority, int] = {
    TicketPriority.URGENT: 4,
    TicketPriority.HIGH: 3,
    TicketPriority.MEDIUM: 2,
    TicketPriority.LOW: 1,
}


@dataclass(frozen=True)
class AgentSnapshot:
    """Dữ liệu thô về một Agent tại thời điểm gợi ý — không có logic tính điểm."""

    agent_id: UUID
    full_name: str
    email: str
    skill_level: int              # 0 = chưa ghi nhận chuyên môn cho loại này
    open_tickets: int
    weighted_load: int
    last_login_at: datetime | None


@dataclass(frozen=True)
class ScoredAgent:
    agent_id: UUID
    full_name: str
    email: str
    score: float
    skill_level: int
    open_tickets: int
    weighted_load: int
    on_duty: bool
    reason: str


class AssigneeScorer:
    """LỚP THUẦN — nhận dữ liệu, trả điểm. Không chạm database, không đọc giờ.

    `now` và mọi số liệu đều được truyền vào, nên toàn bộ ca biên (Agent chưa
    có kỹ năng, Agent quá tải, ngoài giờ làm việc) kiểm thử được bằng unit
    test chạy trong mili-giây.
    """

    def __init__(
        self,
        *,
        w_skill: float | None = None,
        w_load: float | None = None,
        w_duty: float | None = None,
        max_load: int | None = None,
    ) -> None:
        self.w_skill = w_skill if w_skill is not None else settings.SUGGEST_WEIGHT_SKILL
        self.w_load = w_load if w_load is not None else settings.SUGGEST_WEIGHT_LOAD
        self.w_duty = w_duty if w_duty is not None else settings.SUGGEST_WEIGHT_DUTY
        self.max_load = max_load if max_load is not None else settings.SUGGEST_MAX_LOAD

    def score(self, snapshot: AgentSnapshot, *, on_duty: bool) -> float:
        skill = min(snapshot.skill_level, MAX_SKILL_LEVEL) / MAX_SKILL_LEVEL
        load = 1.0 - min(snapshot.weighted_load / self.max_load, 1.0) if self.max_load else 1.0
        duty = 1.0 if on_duty else OFF_DUTY_FACTOR
        return self.w_skill * skill + self.w_load * load + self.w_duty * duty

    def rank(
        self,
        snapshots: list[AgentSnapshot],
        *,
        on_duty_of: dict[UUID, bool],
        category_name: str | None,
        top_n: int = 3,
    ) -> list[ScoredAgent]:
        scored = [
            self._build(s, on_duty=on_duty_of.get(s.agent_id, False), category_name=category_name)
            for s in snapshots
        ]
        # Sắp xếp phụ theo tải rồi theo tên: hai Agent cùng điểm phải ra cùng
        # một thứ tự ở mọi lần gọi, nếu không giao diện sẽ nhảy lung tung.
        scored.sort(key=lambda a: (-a.score, a.weighted_load, a.full_name))
        return scored[:top_n]

    def _build(
        self, snapshot: AgentSnapshot, *, on_duty: bool, category_name: str | None
    ) -> ScoredAgent:
        return ScoredAgent(
            agent_id=snapshot.agent_id,
            full_name=snapshot.full_name,
            email=snapshot.email,
            score=round(self.score(snapshot, on_duty=on_duty), 4),
            skill_level=snapshot.skill_level,
            open_tickets=snapshot.open_tickets,
            weighted_load=snapshot.weighted_load,
            on_duty=on_duty,
            reason=self.explain(snapshot, on_duty=on_duty, category_name=category_name),
        )

    @staticmethod
    def explain(
        snapshot: AgentSnapshot, *, on_duty: bool, category_name: str | None
    ) -> str:
        """Lý do đọc được cho người — bắt buộc theo AC của US-20.

        Một điểm số 0.72 không giúp Agent trưởng quyết định gì. "Chuyên môn
        Mạng (mức 3), đang mở 2 ticket, đang trong ca trực" thì có.
        """
        parts: list[str] = []
        if category_name and snapshot.skill_level > 0:
            parts.append(f"chuyên môn {category_name} (mức {snapshot.skill_level})")
        elif category_name:
            parts.append(f"chưa ghi nhận chuyên môn {category_name}")
        else:
            parts.append("ticket chưa phân loại nên chưa xét chuyên môn")

        if snapshot.open_tickets == 0:
            parts.append("đang rảnh")
        else:
            parts.append(f"đang mở {snapshot.open_tickets} ticket (tải {snapshot.weighted_load})")

        parts.append("đang trong ca trực" if on_duty else "ngoài ca trực")
        sentence = ", ".join(parts)
        # KHÔNG dùng str.capitalize(): nó hạ chữ thường phần còn lại và biến
        # "Mạng & Internet" thành "mạng & internet" — tên loại sự cố do Admin
        # đặt, viết hoa thế nào là quyết định của họ.
        return sentence[:1].upper() + sentence[1:]


class AssigneeSuggestionService:
    """Ghép dữ liệu từ database rồi giao cho `AssigneeScorer` chấm điểm."""

    def __init__(
        self,
        session: Session,
        scorer: AssigneeScorer | None = None,
        calendar: BusinessCalendar | None = None,
    ) -> None:
        self.session = session
        self.scorer = scorer or AssigneeScorer()
        self._calendar = calendar

    def suggest(
        self, ticket: Ticket, *, now: datetime, top_n: int | None = None
    ) -> list[ScoredAgent]:
        snapshots = self.load_snapshots(ticket.category_id)
        if not snapshots:
            return []
        on_duty = {s.agent_id: self.is_on_duty(s.last_login_at, now) for s in snapshots}
        return self.scorer.rank(
            snapshots,
            on_duty_of=on_duty,
            category_name=self._category_name(ticket.category_id),
            top_n=top_n if top_n is not None else settings.SUGGEST_TOP_N,
        )

    def load_snapshots(self, category_id: UUID | None) -> list[AgentSnapshot]:
        """Một truy vấn duy nhất cho toàn bộ Agent.

        Vòng lặp "với mỗi Agent, đếm ticket đang mở" là N+1 kinh điển, và nó
        chạy mỗi lần Agent trưởng mở một ticket.

        `category_id` là None khi ticket chưa được phân loại — khi đó mọi Agent
        có `skill_level = 0` và thứ hạng do tải quyết định. Đó là hành vi đúng:
        chưa biết loại sự cố thì không có cơ sở nói ai giỏi hơn ai.
        """
        # ★ Nhánh `Ticket.id IS NULL` là BẮT BUỘC. Đây là LEFT JOIN: Agent
        # không có ticket nào đang mở vẫn sinh ra một dòng với mọi cột ticket
        # bằng NULL. Khi đó `case(..., value=priority)` không khớp khoá nào và
        # rơi vào `else_=1`, nên Agent đang rảnh bị tính tải bằng 1 — giao
        # diện hiện "đang rảnh" ngay cạnh "tải 1", và mọi Agent rảnh đều bị
        # trừ điểm như nhau. `else_=1` vẫn giữ, cho mức ưu tiên lạ trong tương lai.
        weight = case(
            (Ticket.id.is_(None), 0),
            else_=case(PRIORITY_WEIGHT, value=Ticket.priority, else_=1),
        )

        # ★ Chỉ join `agent_skills` khi ĐÃ biết loại sự cố. Join chỉ theo
        # agent_id sẽ trả về một dòng cho MỖI kỹ năng của Agent, và phép
        # count(tickets) bị nhân lên đúng bằng số kỹ năng — một Agent có 5 kỹ
        # năng bỗng nhiên "đang mở 15 ticket" và không bao giờ được gợi ý nữa.
        skill_level = (
            literal(0) if category_id is None else func.coalesce(AgentSkill.level, 0)
        )
        group_by = [User.id, User.full_name, User.email, User.last_login_at]

        stmt = select(
            User.id,
            User.full_name,
            User.email,
            User.last_login_at,
            skill_level.label("skill_level"),
            func.count(Ticket.id).label("open_tickets"),
            func.coalesce(func.sum(weight), 0).cast(Integer).label("weighted_load"),
        ).select_from(User)

        if category_id is not None:
            stmt = stmt.outerjoin(
                AgentSkill,
                (AgentSkill.agent_id == User.id) & (AgentSkill.category_id == category_id),
            )
            group_by.append(AgentSkill.level)

        rows = self.session.execute(
            stmt.outerjoin(
                Ticket,
                (Ticket.assignee_id == User.id) & Ticket.status.in_(OPEN_STATUSES),
            )
            .where(User.role == UserRole.IT_AGENT, User.is_active.is_(True))
            .group_by(*group_by)
        ).all()

        return [
            AgentSnapshot(
                agent_id=row.id,
                full_name=row.full_name,
                email=row.email,
                skill_level=int(row.skill_level or 0),
                open_tickets=int(row.open_tickets or 0),
                weighted_load=int(row.weighted_load or 0),
                last_login_at=row.last_login_at,
            )
            for row in rows
        ]

    def is_on_duty(self, last_login_at: datetime | None, now: datetime) -> bool:
        """Xấp xỉ "đang trong ca trực" từ dữ liệu hiện có.

        ★ LƯỢC BỎ CÓ CHỦ Ý: lược đồ chưa có bảng `agent_shifts`, nên "ca trực"
        ở đây = trong giờ hành chính VÀ có đăng nhập trong `SUGGEST_DUTY_HOURS`
        giờ gần nhất. Đây là xấp xỉ, không phải lịch trực thật.

        Việc còn lại (bảng `agent_shifts` + màn hình xếp ca) thuộc US-20 của
        Lại Duy Đông. Khi có bảng đó, chỉ cần thay thân hàm này — chữ ký và
        toàn bộ test của `AssigneeScorer` giữ nguyên.
        """
        calendar = self._business_calendar()
        # So sánh `now.time()` giống hệt SlaCalculator.due_at(). Cả hệ thống
        # coi dấu thời gian là một múi giờ duy nhất (Celery cũng đặt UTC); đổi
        # quy ước ở riêng chỗ này sẽ khiến "trong ca trực" và "trong giờ SLA"
        # nói hai điều khác nhau về cùng một thời điểm.
        if not calendar.is_workday(now.date()):
            return False
        if not calendar.start_time <= now.time() < calendar.end_time:
            return False
        if last_login_at is None:
            return False
        return now - last_login_at <= timedelta(hours=settings.SUGGEST_DUTY_HOURS)

    def _business_calendar(self) -> BusinessCalendar:
        if self._calendar is None:
            holidays = frozenset(
                row.holiday_date.date()
                for row in self.session.execute(select(Holiday)).scalars().all()
            )
            self._calendar = BusinessCalendar(
                start_hour=settings.BUSINESS_HOUR_START,
                end_hour=settings.BUSINESS_HOUR_END,
                holidays=holidays,
            )
        return self._calendar

    def _category_name(self, category_id: UUID | None) -> str | None:
        if category_id is None:
            return None
        return self.session.execute(
            select(TicketCategory.name).where(TicketCategory.id == category_id)
        ).scalar_one_or_none()
