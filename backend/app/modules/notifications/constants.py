"""Loại thông báo. Thêm loại mới: thêm vào đây rồi tạo migration đổi CHECK constraint."""

NOTIFICATION_TYPES = (
    "TICKET_ASSIGNED",
    "TICKET_STATUS_CHANGED",
    "TICKET_COMMENTED",
    "TICKET_RESOLVED",
    "SLA_AT_RISK",
    "SLA_BREACHED",
    "RATING_REQUESTED",
)
