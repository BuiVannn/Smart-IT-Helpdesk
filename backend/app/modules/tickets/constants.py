"""Enum của module ticket — nguồn sự thật cho máy trạng thái ở docs/design/03 §5."""

from enum import StrEnum


class TicketStatus(StrEnum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_REQUESTER = "PENDING_REQUESTER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class TicketPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class AiStatus(StrEnum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"


class EventType(StrEnum):
    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    UNASSIGNED = "UNASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    RECLASSIFIED = "RECLASSIFIED"
    COMMENTED = "COMMENTED"
    ATTACHMENT_ADDED = "ATTACHMENT_ADDED"
    AI_CLASSIFIED = "AI_CLASSIFIED"
    SLA_WARNED = "SLA_WARNED"
    SLA_BREACHED = "SLA_BREACHED"
    RATED = "RATED"
    REOPENED = "REOPENED"
    AUTO_CLOSED = "AUTO_CLOSED"


class SlaState(StrEnum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    MET = "MET"


class TicketSource(StrEnum):
    WEB = "WEB"
    CHATBOT = "CHATBOT"
    API = "API"


# Trạng thái được coi là "đang mở" — dùng ở nhiều nơi, khai báo một chỗ duy nhất
OPEN_STATUSES = (
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.PENDING_REQUESTER,
)
