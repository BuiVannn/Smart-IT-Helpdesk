"""Tính hạn SLA theo giờ hành chính — LỚP THUẦN, không I/O.

★ Đây là chỗ dễ sai thứ hai của hệ thống. Ca kiểm thử quan trọng nhất:
ticket URGENT (SLA 4 giờ làm việc) tạo lúc 17:00 thứ Sáu **giờ Việt Nam**
phải có hạn 12:00 trưa THỨ HAI — không phải 21:00 thứ Sáu.
(30 phút cuối thứ Sáu + 210 phút từ 8:30 thứ Hai. Tài liệu 03 §6 từng ghi
11:30, sai 30 phút; đã sửa.)

★★ MÚI GIỜ LÀ CHỖ ĐÃ HỎNG MỘT LẦN, ĐỌC KỸ TRƯỚC KHI SỬA.

Mọi dấu thời gian trong database đều là UTC. Giờ hành chính 8:30–17:30 thì
lại là giờ VIỆT NAM. Bản đầu tiên so thẳng `moment.time()` với `8:30` mà
không đổi múi giờ, nên giờ làm việc thực tế thành 15:30–00:30 giờ Việt Nam:
ticket tạo 9 giờ sáng thứ Hai nhận hạn 4 giờ làm việc là **19:30 cùng ngày**,
tức 2 tiếng sau khi văn phòng đóng cửa.

Quy ước từ nay: `due_at()` nhận UTC, đổi sang giờ địa phương để tính, rồi
đổi kết quả **trả về đúng múi giờ của đầu vào**. Bên gọi không cần biết gì.

Nếu PO xác nhận SLA tính 24/7 thay vì giờ hành chính, chỉ cần đặt
business_hours_only=False và logic rút gọn còn một phép cộng.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.tickets.constants import SlaState

AT_RISK_RATIO = 0.25  # còn <= 25% NGÂN SÁCH GIỜ LÀM VIỆC thì cảnh báo


@dataclass
class BusinessCalendar:
    """Lịch làm việc. holidays là tập ngày nghỉ (không tính vào SLA)."""

    start_hour: float = 8.5  # 8:30
    end_hour: float = 17.5  # 17:30
    workdays: frozenset[int] = frozenset({0, 1, 2, 3, 4})  # thứ 2 → thứ 6
    holidays: frozenset[date] = field(default_factory=frozenset)
    # Giờ hành chính là giờ ĐỊA PHƯƠNG. Ngày nghỉ trong `holidays` cũng là
    # ngày theo lịch địa phương — 30/4 là 30/4 ở Việt Nam, không phải ở UTC.
    timezone: str = "Asia/Ho_Chi_Minh"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def to_local(self, moment: datetime) -> datetime:
        """Đổi sang giờ địa phương. Dấu thời gian thiếu múi giờ coi là UTC.

        Coi naive là UTC chứ không phải là giờ địa phương: mọi cột
        `TIMESTAMPTZ` trong database đều trả về UTC, và một bản ghi cũ lỡ
        mất tzinfo thì đoán UTC vẫn đúng, còn đoán giờ Việt Nam sẽ lệch 7 giờ.
        """
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment.astimezone(self.tz)

    @property
    def minutes_per_day(self) -> int:
        return int((self.end_hour - self.start_hour) * 60)

    def _to_time(self, hour_float: float) -> time:
        return time(int(hour_float), int(round((hour_float % 1) * 60)))

    @property
    def start_time(self) -> time:
        return self._to_time(self.start_hour)

    @property
    def end_time(self) -> time:
        return self._to_time(self.end_hour)

    def is_workday(self, d: date) -> bool:
        return d.weekday() in self.workdays and d not in self.holidays

    def at_local(self, d: date, t: time) -> datetime:
        """Dựng một mốc giờ ĐỊA PHƯƠNG từ ngày và giờ."""
        return datetime.combine(d, t, tzinfo=self.tz)

    def next_workday_start(self, moment: datetime) -> datetime:
        """Thời điểm bắt đầu làm việc kế tiếp kể từ moment (giờ địa phương)."""
        local = self.to_local(moment)
        d = local.date()
        # Nếu hôm nay còn làm việc và chưa tới giờ mở cửa
        if self.is_workday(d) and local.time() < self.start_time:
            return self.at_local(d, self.start_time)
        # Ngược lại: tìm ngày làm việc tiếp theo
        d += timedelta(days=1)
        while not self.is_workday(d):
            d += timedelta(days=1)
        return self.at_local(d, self.start_time)


class SlaCalculator:
    """Tính hạn SLA. Nhận vào dữ liệu, trả ra kết quả — không chạm DB."""

    def __init__(self, calendar: BusinessCalendar | None = None) -> None:
        self.calendar = calendar or BusinessCalendar()

    def due_at(self, start: datetime, minutes: int, business_hours_only: bool = True) -> datetime:
        """Cộng `minutes` phút LÀM VIỆC vào `start`, trả về hạn chót.

        Nhận và trả về CÙNG MỘT MÚI GIỜ với `start` (thực tế là UTC). Toàn bộ
        phép tính bên trong chạy ở giờ địa phương — xem chú thích đầu file.
        """
        if not business_hours_only:
            return start + timedelta(minutes=minutes)

        goc = start.tzinfo or UTC
        cal = self.calendar
        cursor = cal.to_local(start)
        remaining = minutes

        # Nếu bắt đầu ngoài giờ làm việc, dời tới đầu giờ làm việc kế tiếp
        if not cal.is_workday(cursor.date()) or cursor.time() >= cal.end_time:
            cursor = cal.next_workday_start(cursor)
        elif cursor.time() < cal.start_time:
            cursor = cal.at_local(cursor.date(), cal.start_time)

        while remaining > 0:
            end_of_day = cal.at_local(cursor.date(), cal.end_time)
            available = int((end_of_day - cursor).total_seconds() // 60)

            if remaining <= available:
                return (cursor + timedelta(minutes=remaining)).astimezone(goc)

            remaining -= available
            cursor = cal.next_workday_start(end_of_day)

        return cursor.astimezone(goc)

    def business_minutes_between(self, start: datetime, end: datetime) -> int:
        """Số phút LÀM VIỆC giữa hai mốc. Âm hoặc đảo chiều trả về 0.

        ★ Cần cho việc đánh giá `AT_RISK` cho đúng. Tài liệu 03 §6 định nghĩa
        `AT_RISK` là "còn ≤ 25% thời gian", và bản đầu tiên lấy thời gian
        đồng hồ treo tường: ticket URGENT tạo 17:00 thứ Sáu có hạn 11:30 thứ
        Hai, tổng 66,5 giờ, 25% là 16,6 giờ ⇒ ticket **chuyển vàng từ tối Chủ
        nhật**, khi chưa tiêu một phút giờ làm việc nào. Sáng thứ Hai cả hàng
        chờ vàng khè và Agent học cách bỏ qua màu — cảnh báo mất tác dụng.
        """
        if end <= start:
            return 0

        cal = self.calendar
        cursor = cal.to_local(start)
        finish = cal.to_local(end)
        total = 0

        while cursor < finish:
            if not cal.is_workday(cursor.date()) or cursor.time() >= cal.end_time:
                cursor = cal.next_workday_start(cursor)
                continue
            if cursor.time() < cal.start_time:
                cursor = cal.at_local(cursor.date(), cal.start_time)
                continue

            end_of_day = min(cal.at_local(cursor.date(), cal.end_time), finish)
            total += int((end_of_day - cursor).total_seconds() // 60)
            cursor = end_of_day
            if cursor < finish:
                cursor = cal.next_workday_start(cursor)

        return total

    def state(
        self,
        *,
        created_at: datetime,
        due_at: datetime | None,
        resolved_at: datetime | None,
        now: datetime,
        paused_seconds: int = 0,
    ) -> SlaState:
        """Trạng thái SLA để hiển thị. Thời gian chờ người dùng không tính vào."""
        if due_at is None:
            return SlaState.ON_TRACK

        effective_due = due_at + timedelta(seconds=paused_seconds)

        if resolved_at is not None:
            return SlaState.MET if resolved_at <= effective_due else SlaState.BREACHED
        if now > effective_due:
            return SlaState.BREACHED

        # ★ Tỉ lệ tính trên NGÂN SÁCH GIỜ LÀM VIỆC, không phải thời gian đồng
        # hồ treo tường — xem `business_minutes_between()` để biết vì sao.
        total = self.business_minutes_between(created_at, effective_due)
        left = self.business_minutes_between(now, effective_due)
        if total > 0 and left / total <= AT_RISK_RATIO:
            return SlaState.AT_RISK
        return SlaState.ON_TRACK
